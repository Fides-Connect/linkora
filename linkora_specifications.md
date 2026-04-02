# Linkora — System Behaviours & Use Cases (Lastenheft)

> **Living document.** Every session that surfaces a new behaviour, edge case, or invariant must append it to the relevant section.
>
> **Purpose:** This file describes *what* the system shall do and *how* it shall behave in each scenario. Implementation details (class names, file paths, internal tooling) do not belong here.
>
> **Agents: load only the section(s) relevant to your current task.**

---

## 1. Overall System Purpose

- The platform is an AI voice/chat assistant that matches users (service seekers) to service providers.
- The AI assistant's persona is named **Elin**.
- Every user interaction either ends with a matched provider list, a submitted service request, or an onboarding of the user as a new provider.
- The system supports two interaction modes:
  - **Voice mode**: the user speaks; the AI responds with synthesised speech and text.
  - **Text mode**: the user types; the AI responds with text only. No audio greeting is synthesized or played on connection, but a text greeting is still dispatched.
- All AI responses and prompts are language-aware. The language is set per session by the client and must be respected throughout the entire conversation. It must never be hardcoded.
- **Demo / Seeding Mode**: In development and demo environments, the system may pre-populate the search index with synthetic provider profiles to enable end-to-end testing of the provider-search flow. This is a demo-only behavior; production environments must never seed synthetic data.
- **External Provider Search (Google Places)**: The platform supports an external provider search mode backed by the Google Places API. This integration is exclusive to lite mode (`AGENT_MODE=lite`) and is always active when that mode is in use. In full mode, provider discovery uses only the internal search index (Weaviate); Google Places is never queried.
- **Configurable Agent Mode**: The platform supports two named agent modes that control the active conversation stage machine, the prompts used in each stage, and the tools available during a session. The mode is selected by a server-side configuration parameter; it applies to the entire server process and cannot be changed per-session or mid-session. The low-level transport and audio state machine is shared and unchanged across all modes. If an unknown mode is configured, the system must log a warning and fall back to the default mode.

---

## 2. Data Integrity Rules

### 2.1 Source of Truth

- Firestore is the authoritative data store. All persistent state (users, service requests, competencies, reviews, AI conversations) is written there first.
- The search index (Weaviate) is a read-optimised cache. It mirrors provider competencies for vector and hybrid search. It is never the source of truth.
- **Name Lookup Precedence**: The user's display name shown in AI greetings and conversation history is always read from Firestore, which is the authoritative record. Client-supplied name fields in login sync requests are only applied as updates when the incoming value is non-empty and are never used as the name for live session greeting without first reading the Firestore record.

### 2.2 Provider Visibility in Search

- A provider appears in search results only if their profile in the search index is marked as an active service provider.
- If a user's profile is absent from the search index, they return zero results regardless of their stored competencies.
- When zero results are returned, the system must log a diagnostic entry indicating how many competencies with the active-provider flag exist, to distinguish between a flag issue and a vocabulary mismatch.

### 2.3 Provider Flag Consistency (Self-Heal)

- If the authoritative database shows a user is not a service provider but the user already has competencies stored, the system shall automatically upgrade the user's status to service provider on the next login.
- This self-healing must be idempotent — running it multiple times must not corrupt data.
- The client application always sends `is_service_provider: false` during login sync. The system must not trust this value; it must read the authoritative value from the database before writing to the search index.

### 2.4 Search Index Self-Heal on Login

- On every user login, the system must verify that the user's search-index node exists.
- If the node is absent, the system must immediately recreate it from authoritative data and re-sync all competencies.
- This prevents a user from becoming invisible in provider searches after an index reset.

### 2.5 AI Conversation TTL

- AI conversation documents expire automatically after 30 days.
- Resetting a conversation session clears the in-memory chat history only. It does not delete the persisted conversation document.

### 2.6 Topic Title Length

- Automatically generated conversation topic titles must not exceed 300 characters before being stored. Titles exceeding the 300-character limit must be truncated gracefully at the nearest word or valid Unicode character boundary. Hard truncation at exactly 300 bytes/characters must not split multi-byte characters, which would corrupt the string.

### 2.7 Search Cache Outage

- If Weaviate is entirely unreachable during login or search, the system must not fail the entire user session. It must degrade gracefully: login succeeds with a logged warning, and searches return a standardized "Search temporarily unavailable" error to the AI to handle via `RECOVERY`.
- When the provider search backend is unreachable specifically during the `FINALIZE` stage, the system must immediately transition to `RECOVERY` rather than presenting zero results as a genuine empty-match outcome. The `RECOVERY` message must indicate that the search was temporarily unavailable, not that no matching provider was found.
- *(Lite mode only — see §14.4)* When the Google Places API is unreachable or returns an error during a lite-mode `FINALIZE` stage, the system must not fail. It must inform the user that the external search is temporarily unavailable, then proceed using only the internal search index results. The degradation must be transparent to the user (e.g. "I was unable to reach Google Maps right now, so I am searching our registered providers instead.").

---

## 3. Conversation Flow

### 3.1 Session Start & Dynamic Initialization

- **Voice mode**: the AI greets the user by his name immediately upon connection.
- **Text mode (LLM-Driven Initialization)**: The AI starts in the `GREETING` stage. Instead of dispatching a hardcoded text greeting immediately on page load, the system uses an LLM-driven initialization to provide a natural, dynamic greeting. 
  - If the session is initiated with a buffered user message (e.g., from a dormant UI waking up), the system wraps the message in a silent system tag (e.g., `[System Event: User reconnected and sent the following message]`) and passes it directly to the LLM. The LLM processes the greeting and the user's intent simultaneously, skipping autonomous text emission, and transitioning to `TRIAGE`.
  - If no message is buffered (a completely fresh start), the system prompts the LLM to generate a fresh, context-aware greeting to initiate the chat before autonomously transitioning to `TRIAGE`.
- **Language Enforcement**: If the WebSocket connection lacks a `language` parameter or provides an invalid one, the system defaults to the user's REST-stored settings language, or `"en"` if none exists. The language parameter provided by the client strictly overrides the REST-stored user setting for the duration of that session. The conversation language cannot be changed mid-session.
- **Unsupported Client Language**: If the client requests a language via WebSocket that the LLM is not localized or tested for (e.g., passing a rare dialect code), the system must fallback to English (`"en"`) and inform the user of the fallback in the first turn.
- **Cross-Lingual Handling**: The AI prompt must strictly enforce that all responses remain in the session-defined language. If the user speaks in a different language, the AI must explicitly translate or acknowledge the input in the configured system language (e.g., "I see you're speaking German, but I am configured for English right now. How can I help?").

### 3.2 Conversation Stages

The conversation progresses through a finite set of named stages. Each stage represents a distinct phase of the dialogue with its own prompt behaviour and transition rules.

| Stage                 | Purpose                                                                                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `GREETING`            | **Welcome.** The AI greets the user by name (dynamically derived) and checks whether they have an open service request, then invites them to share their need.|
| `TRIAGE`              | **Scoping.** The AI acts as a service coordinator. It must collect a strict minimum set of requirements (defined in Section 3.4) before it is permitted to transition to CONFIRMATION. It also detects provider-management intent and routes accordingly. |
| `CLARIFY`             | **Disambiguation.** Used when the request is too ambiguous to scope. The AI asks exactly one targeted question and immediately returns to `TRIAGE`.            |
| `TOOL_EXECUTION`      | **Data retrieval.** An intermediate stage while a data operation runs (e.g. fetching open requests or favorites). Control returns to `TRIAGE`, `CONFIRMATION`, or `FINALIZE` once the tool completes. |
| `CONFIRMATION`        | **Pre-commit check.** The AI summarises the scoped request in 2–3 sentences and asks the user to confirm before proceeding to provider matching.               |
| `FINALIZE`            | **Provider matching and presentation.** A multi-turn, tool-driven stage where the system searches for providers, presents them, and waits for the user to make a decision using explicit functional tools. |
| `RECOVERY`            | **Error / confusion recovery.** The AI calmly acknowledges the issue without asking the user to restart, then steers back to `TRIAGE` as soon as any service context is given. |
| `COMPLETED`           | **Post-request wrap-up.** The current service flow (request submitted or onboarding finished) has concluded. The AI asks warmly if the user needs anything else. |
| `PROVIDER_PITCH`      | **Recruitment offer.** The AI invites the user—once per 30-day window—to join as a service provider. Fires automatically when the user is eligible and `COMPLETED` is reached. |
| `PROVIDER_ONBOARDING` | **Skill management.** Multi-turn conversation to add, update, or remove the user's service competencies. Accessible both after accepting the pitch and directly from `TRIAGE`. |

The system must enforce legal transitions only. Illegal stage transitions must be rejected and silently ignored.

| Current Stage         | Allowed Next Stages                                                                         |
|-----------------------|---------------------------------------------------------------------------------------------|
| `GREETING`            | `TRIAGE`                                                                                    |
| `TRIAGE`              | `CONFIRMATION`, `CLARIFY`, `TOOL_EXECUTION`, `RECOVERY`, `PROVIDER_ONBOARDING`              |
| `CLARIFY`             | `TRIAGE`                                                                                    |
| `TOOL_EXECUTION`      | `TRIAGE`, `CONFIRMATION`, `FINALIZE`                                                        |
| `CONFIRMATION`        | `FINALIZE`, `TRIAGE`                                                                        |
| `FINALIZE`            | `COMPLETED`, `RECOVERY`, `TRIAGE`                                                           |
| `RECOVERY`            | `TRIAGE`                                                                                    |
| `COMPLETED`           | `PROVIDER_PITCH`, `TRIAGE`                                                                  |
| `PROVIDER_PITCH`      | `PROVIDER_ONBOARDING`, `COMPLETED`, `TRIAGE`                                                |
| `PROVIDER_ONBOARDING` | `COMPLETED`, `TRIAGE`                                                                       |

**Transition notes:**

- **Atomic Stage Output**: When the system autonomously fast-paths through a stage — most commonly `TRIAGE → CONFIRMATION` because the user's initial request was already complete — the originating stage (`TRIAGE`) must emit only the `signal_transition` call and must not produce any natural-language response text. All user-facing communication is the sole responsibility of the destination stage (`CONFIRMATION`). This prevents stacking of redundant acknowledgements across consecutive stage outputs.
- **Strict Confirmation Gate**: The system must strictly enforce that `FINALIZE` can only be entered from `CONFIRMATION` or `TOOL_EXECUTION`. The AI is mathematically forbidden from transitioning directly from `TRIAGE` to `FINALIZE` without user approval.
- `CONFIRMATION → FINALIZE`: the system automatically performs a provider search. The routing is handled by the backend orchestrator based on the search results (see §6.11).
- `FINALIZE → COMPLETED`: The LLM inside `FINALIZE` **does not use the `signal_transition` tool.** This transition is automatically forced by the backend orchestrator when the LLM successfully executes the `accept_provider` tool. The `COMPLETED` follow-up response generated after this automated transition must be triggered without replaying the user's prior utterance (e.g. a location or date answer) — the orchestrator must inject a neutral input for the `COMPLETED` stage prompt so that the LLM does not misinterpret the prior answer as a new service request and generate a duplicate confirmation message.
- `FINALIZE → TRIAGE`: Triggered automatically by the backend orchestrator when the LLM executes the `cancel_search` tool, or if the user exhausts the cached provider list. It is also triggered pre-emptively by the orchestrator (bypassing the FINALIZE LLM) if the initial search returns exactly 0 results.
- **FINALIZE Safety Fallback Limitation**: Because `FINALIZE` relies on the user to make a choice (and intentionally omits a generic state transition signal), the standard orchestrator safety fallback (forcing `RECOVERY` when a stage does not emit a transition) **must be disabled for the `FINALIZE` stage.** The stage naturally waits for user input.
- `COMPLETED → PROVIDER_PITCH`: fires automatically (without an explicit LLM call) when the user is pitch-eligible (see §4). The LLM never needs to call this transition itself.
- `COMPLETED → TRIAGE`: triggered when the user indicates they have another need after the current flow concludes.
- `PROVIDER_PITCH → TRIAGE`: triggered when the user, during the pitch, says they actually want to find a service provider rather than become one.
- `PROVIDER_ONBOARDING → TRIAGE`: triggered when the user declines the provider role (STEP 0 "no") or switches intent to finding a service instead of managing their own skills.
- `PROVIDER_ONBOARDING → COMPLETED`: in addition to the standard stage transition, the system resets the per-request context (problem description, scoped request, provider results) so that the follow-up `COMPLETED` flow starts without stale service-request state from any prior session.
- Any back-transition to `TRIAGE` from `COMPLETED`, `FINALIZE`, `PROVIDER_PITCH`, or `PROVIDER_ONBOARDING` clears the per-request context so the new scoping session starts clean. **However, the exact user utterance that triggered the back-transition must be preserved and injected as the first prompt of the new `TRIAGE` session.**
- A stage transition that targets the stage the conversation is already in is silently ignored (self-loop guard).

### 3.3 Streaming Delivery

- Each autonomous follow-up sub-stream (triggered after a stage transition) is delivered as an independent series of `chat` protocol messages. When a stage transition is silent (e.g. the fast-path `TRIAGE → CONFIRMATION`), the originating stage produces no chat messages at all; only the destination stage produces output. The client opens a new chat bubble for each logically distinct server response. A new bubble boundary is signalled by the server beginning a new sequence of `chat` messages; specifically, a complete (non-chunk) message (`isChunk: false`) always starts its own bubble, and a fresh sequence of `isChunk: true` fragments following a prior completed message starts a new bubble.
- **Response Deduplication**: The system prompt for every stage must explicitly forbid repeating an acknowledgement of the user's request if that stage was reached via a silent fast-path transition from a previous stage. If the LLM's generated output for a given stage begins with a paraphrase of the user's request that was already acknowledged in the immediately preceding stage output, the duplicate sentence must be stripped before delivery. Each stage may only acknowledge the user's intent once per conversational turn across all sub-streams in that turn.
- If the LLM output contains verbatim tool-call invocations as text (e.g. `signal_transition(target_stage="finalize")`), those patterns must be stripped from the streamed text before delivery to the client. Only text matching a registered tool name is stripped.
- When the `FINALIZE` provider-search is actively running, any new user input (voice or text) must be rejected. The system sends a bilingual acknowledgement (German and English) informing the user that the search is still in progress, and does not interrupt the search.
- If the user disconnects or the session is intentionally terminated while a `FINALIZE` search is actively running, the background search tasks must be aborted to free system resources.
- **Silent Tool Execution**: The LLM must never narrate or announce internal state transitions, database searches, or tool executions in natural language (e.g., 'Let me search the database'). If a transition or search is required, the LLM must emit the transition signal silently. Status updates regarding searches are handled exclusively by the client UI interpreting the `runtime-state`.
- **Cascading Transitions Within a Single Turn**: When a stage transition triggers an autonomous follow-up LLM call that itself emits another transition (e.g., `TRIAGE → CONFIRMATION → TRIAGE → CONFIRMATION`), the system must continue processing each subsequent stage until no pending transitions remain or a safety depth limit is reached. No pending stage transition result shall be silently discarded mid-turn. The user must always receive a natural-language response from the final resolved stage, never silence.

### 3.4 Clarification & Minimum Required Information (MRI)

The AI must not transition from TRIAGE (or CLARIFY) to CONFIRMATION until the user's request contains sufficient detail. **MRI requirements differ by agent mode** — see §14.3 for the lite-mode definition. The rules below apply to `full` mode.

Sufficient detail is strictly defined as successfully collecting ALL of the following:

- **Core Intent**: The primary service required (e.g., installing lights, fixing a leak).
- **Contextual Details (Minimum 3)**: At least three specific details defining the scope of the work (e.g., for lighting: indoor vs. outdoor, type of fixtures, ceiling height, current wiring status, number of rooms).
- **Availability or Urgency**: The user's preferred time slot (e.g., "next Tuesday morning", "weekends") OR the urgency of the request (e.g., "emergency", "flexible").

**Probing Rules:**
- If the initial user request lacks any of these MRI elements, the AI must remain in TRIAGE (or use CLARIFY) to ask targeted questions to gather the missing data.
- To avoid overwhelming the user, the AI must ask a maximum of 1 to 2 questions per turn. It must weave these naturally into the conversation rather than presenting a robotic checklist.
- Only once all MRI criteria are met should the AI move to the CONFIRMATION stage to summarise the fully fleshed-out request.

**Extended Context (soft-ask — collected after MRI is satisfied):**
Once the three MRI elements are gathered, the AI opportunistically collects the following extras with at most one natural question each. None of these block the flow; the AI must not re-ask if the user dismisses or skips them.
- **Location** *(full mode)*: Location is a soft-ask for in-person services (plumbing, cleaning, electrical work, etc.): the AI asks once "Where is the work needed — which city or area?" and skips it entirely for remote/digital work. In full mode, location is never a hard MRI gate. For the lite-mode location rule (hard MRI requirement), see §14.4.
- **Budget**: The AI asks once if clearly relevant: "Do you have a rough budget in mind?" Any answer — including "no idea" or silence — is accepted without follow-up.
- **Exact dates**: If the user stated a relative timeframe (e.g. "next Tuesday"), the AI resolves it to a concrete calendar date internally. The user is not asked to re-state it as an ISO date.

**User Override Exception:**
- If the user explicitly refuses to provide more details or forces the search (e.g., "I don't know the details, just find me someone right now!"), the AI must immediately skip the remaining MRI checks and proceed to CONFIRMATION.

For ambiguity resolution, the AI may enter CLARIFY to ask one targeted question before returning to TRIAGE.

### 3.5 Interrupt Handling

- If the user speaks or sends a message while the AI is actively responding, the AI's current response must be cancelled before a new one is generated.
- Empty or noise-only audio that does not produce a valid text transcript must not trigger an interrupt of the AI's current response.
- When the STT stream has received no non-empty transcript for 120 consecutive seconds (measured from the first empty final result), the system must close the current gRPC stream and open a fresh one. The idle timer is reset by any non-empty transcript (interim or final). This prevents reaching the STT service's hard 305-second stream-duration limit during prolonged silence.
- When a response is interrupted, any partial user input that triggered the interrupt must be preserved and prepended to the user's next message, so the full accumulated request is processed coherently in the following turn.
- The system must not produce a situation where the conversation history contains consecutive user messages with no AI reply between them, as this causes the AI to lose conversational context.
- **Interrupting State-Mutating Tools:** Data mutation tools (e.g., executing a `cancel_service_request` during `TOOL_EXECUTION`) must execute atomically. Once triggered by the backend, they cannot be rolled back by a user interrupt. However, if an interrupt arrives *before* the tool-call chunk is completely parsed and executed by the backend, the tool execution is safely aborted. 
- If a state-mutating tool fails to execute on the backend, but the user has already interrupted the AI's response acknowledging the tool use, the system must forcefully inject the error context into the user's new interrupted prompt so the AI can inform the user that their previous action actually failed.

### 3.6 Rapid Message Bursts

- When a user sends multiple messages in rapid succession (voice or text), each new message cancels the previous in-flight response.
- The system must coalesce all interrupted fragments so that the final response addresses the full intent of all the burst messages, not just the last one.
- The LLM prompt must be instructed to prioritize the chronological end of the coalesced string when deriving the final intent (e.g., if the user says "I need a plumber" then immediately "Cancel that, I need an electrician").

### 3.7 Session Initialisation Delay

- When the first text message arrives in a session, the system waits up to 2 seconds for session initialisation (user data retrieval) to complete before processing the message. If the timeout is exceeded, the message is processed immediately without user context.
- If the 2-second timeout is exceeded but user data is returned successfully later, it must be injected into the in-memory session whenever it arrives, applying to all future turns.

### 3.8 Response Conciseness and Deduplication

- **Single Acknowledgement Rule**: The AI must acknowledge the user's request or intent at most once per conversational turn, across all stage sub-streams. Redundant re-phrasings of the same intent within the same turn are strictly forbidden.
- **Direct Action**: The AI must not use repetitive conversational filler (e.g., "No problem at all, I can help! Alright, I can certainly help..."). After a single, brief acknowledgement (if any), the AI must proceed immediately to the required stage action — summarising, asking a clarifying question, or executing a tool.
- **Pre-Commit Summary Consolidation**: During the `CONFIRMATION` stage, if the stage was reached via a fast-path transition from `TRIAGE`, the AI must combine any acknowledgement and the confirmation summary into a single cohesive statement. It must not open with a fresh greeting-like preamble before the summary.
- **Silent Fast-Path Transitions**: When `TRIAGE` determines that the user's request is already complete and transitions immediately to `CONFIRMATION`, the `TRIAGE` LLM call must emit the `signal_transition` signal only and produce no natural-language output. The `CONFIRMATION` stage owns all user-visible text for that turn.

### 3.10 Empty LLM Response Recovery

- If the LLM orchestration pipeline produces no visible text across the primary stream and all follow-up streams (e.g., because the model exhausted its output-token budget on internal reasoning without generating a final answer), the system must yield a generic fallback error message to the user. Silent pipeline completion with no user-facing output is not permitted.
- The AI service must disable extended model thinking (thinking_budget=0) for all real-time conversation turns. Extended thinking adds latency and consumes from the output token budget, which can silently exhaust the limit before any response is generated.

### 3.9 Provider Onboarding Competency Injection

- At the start of every `PROVIDER_ONBOARDING` turn, the system pre-fetches the user's current competency list from the authoritative data store and injects it into the LLM prompt context. The LLM must never call a competency-fetch tool explicitly during onboarding turns; the data is always pre-loaded.
- After any competency write or delete operation during an onboarding turn, the competency list is immediately refreshed from the authoritative store before the follow-up LLM call.
- If the AI signals `completed` at the end of a `PROVIDER_ONBOARDING` turn without having called any write operation in that turn, this is treated as "user chose no changes" and is processed normally with no error.

---

## 4. Provider Pitch Flow

### 4.1 Eligibility

The AI shall pitch the provider opportunity to a user only when **all four** of the following conditions are true:

1. The user is not already a service provider.
2. The user's provider-pitch opt-in timestamp has been set (i.e. not null). If explicitly `null` (e.g. not yet synchronized by login), the user is strictly ineligible.
3. The user has not permanently opted out (the timestamp must not equal the permanent opt-out sentinel).
4. At least 30 days have elapsed since the user was last asked.

New users have their timestamp pre-set to 60 days in the past, so the first eligible completed conversation triggers the pitch. Just before entering `PROVIDER_PITCH`, the system must perform a real-time check against the authoritative database to ensure `is_service_provider` is still false, overriding the in-memory session context.

### 4.2 Auto-Trigger

- The pitch is triggered automatically when a conversation reaches `COMPLETED` and the user is eligible.
- The conversation advances to `PROVIDER_PITCH`; no explicit user action is required.

### 4.3 User Responses to the Pitch

+------------+-----------------------------------------------------------------------------------+
| Response   | System Action                                                                     |
+============+===================================================================================+
| `accepted` | Transition to `PROVIDER_ONBOARDING`. **Crucially, the system does not write       |
|            | `is_service_provider = true` to Firestore yet.** The provider flag and the        |
|            | `provider_pitch_last_asked` timestamp are only updated upon the successful        |
|            | database save of the user's first skill batch. If the user abandons onboarding    |
|            | mid-way, they remain eligible for a future pitch.                                 |
+------------+-----------------------------------------------------------------------------------+
| `not_now`  | Immediately update the `provider_pitch_last_asked` timestamp to the current time, |
|            | resetting the 30-day cooldown clock.                                              |
+------------+-----------------------------------------------------------------------------------+
| `never`    | If the user's intent is to stop being asked or they state they never want to      |
|            | provide services, the system stores the permanent opt-out sentinel in             |
|            | `provider_pitch_last_asked`. The user is rendered strictly ineligible for future  |
|            | pitches and is never asked again.                                                 |
+------------+-----------------------------------------------------------------------------------+

- Any `decision` value that is not `"accepted"` or `"never"` is treated as `"not_now"`.
- After a pitch response is recorded, the in-session user context is immediately updated in memory so that the pitch eligibility check will not re-evaluate as eligible during the same conversation.

---

## 5. Provider Onboarding Flow

- Onboarding is a multi-turn skill collection conversation.
- The AI asks at most 2 questions per turn to avoid overwhelming the user.
- All collected skill data is held in the session draft until the user confirms.
- The session ends with the AI presenting a Markdown summary of collected skills, followed by saving the full batch.
- Onboarding draft state is session-scoped. If the session drops, the draft is lost and onboarding must restart.
- **Concurrent Sessions Draft Invalidation:** At the start of every `PROVIDER_ONBOARDING` turn, the system refreshes the user's competency list from the authoritative data store. If the count of live competencies differs from the count at the time the draft was created (indicating that another session or the REST API modified the data), the in-memory onboarding draft is immediately discarded. The user is informed of the external change before the turn continues, so they can start the draft anew with accurate data.
- Existing providers may also enter onboarding to update their skills (triggered from the triage stage).
- When a user who is already marked as a service provider enters the `PROVIDER_ONBOARDING` stage, the system skips the provider-intent confirmation step (STEP 0). The AI proceeds directly to reading and summarising the user's existing competencies.
- **Mid-Onboarding Abandonment:** If a user becomes a provider but closes the app before adding any skills, their profile remains invisible in search. On their next login, if they have exactly 0 competencies, the system must prompt them immediately to finish onboarding or temporarily toggle their search visibility off.

### 5.1 Skill Batch Validation

- For every new skill in a save batch (a skill with no existing identifier), `price_range` is required. If any new skill is missing `price_range`, the entire batch is rejected. The error must name the affected skill titles and instruct that pricing information is required before the batch can be saved.
- If a user wishes to offer a service for free, the `price_range` validation must accept an explicit `0` (integer or string) or `'free'` token. It must not strictly require a monetary range if the intent is volunteer work. A numeric zero value must not raise an error during validation.
- For every new skill, `availability_time` is also required. If any new skill is missing it, the batch is rejected with the affected titles identified.
- If a batch is rejected for missing fields (like `price_range` or `availability_time`), the in-memory session draft must retain the valid skill data. The AI will prompt the user specifically for the missing fields on the failing items.
- `availability_time` is validated against the schema before any data is written. If validation fails, field-level error details and time-format hints are returned, and no partial state is written.
- When writing availability data for a skill, if an existing availability record already exists for that skill, it is updated; otherwise a new record is created. At most one availability record exists per skill.

### 5.2 Skill Deduplication

- When a save batch includes a new skill whose title case-insensitively matches an existing skill for the same user, the system treats it as an update to the existing entry rather than creating a duplicate. No error is returned.

### 5.3 Search Index Self-Heal During Onboarding

- When a skill save or delete operation detects that the user's search-index node is missing, the system self-heals by recreating the node from authoritative data and re-syncing all skills before retrying the original operation. If self-healing fails, the error propagates.

### 5.4 Dropped Connection During Batch Save

- If the WebRTC/WebSocket connection drops exactly while a validated skill batch is being written to Firestore, the server must complete the atomic write. Upon reconnection, the system must not prompt the user to resume an onboarding draft that was already successfully committed.

### 5.5 Onboarding Turn Structure (Step Protocol)

Every `PROVIDER_ONBOARDING` turn follows a deterministic five-step conversation protocol. The AI must not skip or reorder steps.

- **STEP 0 — Provider Intent Gate** (only applies when `is_service_provider` is `False`; skipped entirely for existing providers):
  - If the user's most recent message contains a clear offer signal (e.g. "I could help", "I want to offer my services", "I'd like to share my skills"), the AI calls `record_provider_interest(decision="accepted")` immediately without asking for confirmation.
  - If intent is unclear or ambiguous, the AI asks exactly one direct question: "Would you like to offer your skills as a service provider on Linkora?" If the user answers no, the AI transitions immediately to `TRIAGE`.
  - When `record_provider_interest("accepted")` is called within STEP 0, the AI must **not** call `signal_transition("provider_onboarding")` itself — the system handles re-entry into the next `PROVIDER_ONBOARDING` turn automatically.
  - The `record_provider_interest` tool is called at most once per turn.

- **STEP 1 — Situation Analysis**: The AI reads the pre-fetched competency list. If the list is empty, it welcomes the user as a new provider and moves immediately to collecting their first skill. If the list is non-empty, it summarises the existing skills naturally in 1–2 sentences and invites the user to state what they would like to do.

- **STEP 2 — Intent Classification**: The AI maps the user's response to one of three action modes:
  - `ADD`: registering a skill whose title does not match any existing competency. Before deciding `ADD`, the AI must compare the proposed title (case-insensitively) against every existing entry. A title collision redirects the intent to `UPDATE`.
  - `UPDATE`: modifying an existing competency. The AI uses the `competence_id` from the pre-fetched list. It must never invent a `competence_id`.
  - `REMOVE`: deleting one or more existing competencies by their `competence_id`. If the referenced title is ambiguous, the AI asks for clarification before proceeding.
  - If the user expresses intent to find a service provider rather than manage their own skills, the AI acknowledges in one brief sentence and transitions immediately to `TRIAGE`.
  - If the user states they want no changes, the AI calls `signal_transition(target_stage="completed")` immediately without calling any write tool.

- **STEP 3 — Confirm Before Writing**: Before calling any write tool, the AI presents a plain-language summary of the proposed change and waits for explicit user confirmation. Raw JSON, field names, `competence_id` strings, and HH:MM time values are never surfaced to the user in this summary.

- **STEP 4 — Execute on Confirmation**: When the user confirms, the AI calls the write tool (`save_competence_batch` or `delete_competences`) as the **first action** in that response — no leading text is emitted before the tool call. After the tool result is received:
  - On success: the AI confirms the change warmly in 1–2 sentences. No follow-up question is issued in this same response.
  - On error: the AI apologises briefly and reassures the user that their data has not been lost.

- **STEP 5 — Continue or Complete**: After confirming the write result, the AI asks naturally whether the user wants to make additional changes. If the user says no (e.g. "that's all", "nothing else"), the AI calls `signal_transition(target_stage="completed")` with no additional message. The AI may handle multiple intents in one session (e.g. update one skill, then add another), resolving them one at a time.

### 5.6 Two-Response Ordering Constraint

- A `signal_transition` call and a write tool call (`save_competence_batch` or `delete_competences`) must never appear in the same LLM response.
- The write tool is always emitted in **Response A** (STEP 4); the transition signal is always emitted in **Response B** (STEP 5).
- Even if the user says "yes, that's all" when confirming a change, the write tool still executes first in Response A; the transition is deferred to Response B after the tool result is received.

### 5.7 Availability Data Collection and Interpretation

The AI collects availability for a new skill in a single conversation pass. It asks "when are you usually available?" exactly once and interprets the answer using the following fixed mapping, without asking follow-up questions for clarification of hours:

| User says | Interpreted as |
|---|---|
| "morning" / "in the morning" | 08:00–12:00 on the mentioned day(s) |
| "afternoon" | 12:00–17:00 on the mentioned day(s) |
| "evening" / "after work" / "evenings" | 17:00–21:00 on the mentioned day(s) |
| "from HH" / "after Xpm" with no end time | HH:00–21:00 (21:00 as default end-of-day) |
| "whole day" / "all day" | 08:00–20:00 on the mentioned day(s) |
| "weekdays" (no specific time) | 08:00–20:00 Mon–Fri |
| "at the weekend" / "weekends" | 08:00–20:00 Sat and Sun |
| "flexible" / "anytime" / "any time" / vague (NEW skill) | 08:00–20:00 on all seven days |
| "flexible" / "anytime" / vague (UPDATE) | Omit `availability_time`; it is optional for updates |

- All time values are zero-padded HH:MM (e.g. `09:00`, not `9:00`). Absence days use YYYY-MM-DD format.
- Availability is always described to the user in natural language; raw time strings, field names, and JSON are never shown.
- The AI must not add qualifiers like "a rough estimate is fine" or "no need to be precise" when asking about availability — it asks the question directly and trusts the user's answer.

### 5.8 Competency Save Pipeline

When `save_competence_batch` executes, the following steps occur in order:

1. **Batch validation (price_range)**: `price_range` is required for every new skill (no `competence_id`). A free or volunteer offering must be expressed as `0` or `"free"` — a zero value must not raise a validation error. If any truly new skill is missing `price_range`, the entire batch is rejected; the error names the affected titles. No Firestore write occurs.
2. **Server-side deduplication**: a skill submitted without a `competence_id` whose title case-insensitively matches an existing competency is silently promoted to an update of that entry. Such promoted entries are then exempt from the `availability_time` requirement check (step 3 below).
3. **Batch validation (availability_time)**: `availability_time` is required for every truly new skill (one that is not deduplicated to an update). If any such skill is missing it, the entire batch is rejected with the affected titles named.
4. **Availability schema validation**: the `availability_time` structure of each skill is validated against the schema before any Firestore write. An invalid structure rejects the batch with field-level error details and time-format hints; no partial state is written.
5. **Per-skill Firestore write**: each skill is created or updated in Firestore.
6. **Availability subcollection write**: the `availability_time` data is written to the skill's subcollection. If an existing record is present, it is updated; otherwise a new record is created. At most one availability record may exist per skill. If this write fails for any skill, the entire save operation must fail and propagate the error. Silent success with missing availability data is not permitted.
7. **LLM enrichment** (non-blocking on failure): the enrichment step extracts `skills_list`, `search_optimized_summary`, `price_per_hour`, `availability_tags`, `availability_text`, and `category` from the raw data and writes them back to Firestore. **Crucially, to ensure optimal vector proximity with the search stage, `search_optimized_summary`, `skills_list`, and `availability_tags` must be generated strictly in English. The `search_optimized_summary` must be written in a third-person prose style (e.g., "This provider is...") to perfectly mirror the HyDE query structure, and `skills_list` must extract specific, actionable capabilities.** Enrichment failure is non-fatal; the skill remains saved with raw data intact.
8. **Provider flag & Cooldown**: `is_service_provider = True` is written to both Firestore and the search index simultaneously. If this was the user's first competency (completing their initial onboarding), the system also updates their `provider_pitch_last_asked` timestamp to the current time to reset their pitch cooldown.
9. **Full search-index re-sync**: all of the user's competencies are read from Firestore (the authoritative source), availability tags are derived from the subcollection data for each skill, and the entire competency set is synced to the search index. If the user's search-index node is absent, it is self-healed by recreating it from Firestore before re-syncing.

The `save_competence_batch` execution is **shielded** against mid-write WebSocket disconnections: the coroutine cannot be cancelled once started, ensuring Firestore writes complete atomically even if the session drops.

For `delete_competences`: each deleted competency is removed from Firestore and then from the search index. Errors during search-index removal propagate to the caller.

---

## 6. Service Request Flow

### 6.1 Happy Path

1. User describes a need → stage: `TRIAGE`.
2. AI optionally clarifies → stage: `CLARIFY → TRIAGE`.
3. AI confirms the request with the user → stages: `TRIAGE → CONFIRMATION`.
4. User explicitly confirms the summary.
5. System performs provider search and relies on the Backend Orchestrator to evaluate results and transition → stage: `FINALIZE` (if results > 0).
6. User explicitly accepts a presented provider (LLM calls `accept_provider`) → stage: `COMPLETED`.

- **Mandatory Confirmation Gate:** Regardless of how comprehensively the user defines their request in the initial prompt, the AI must summarize the understood requirements in the `CONFIRMATION` stage and receive an explicit affirmative response from the user before executing the provider search in `FINALIZE`.

### 6.2 Provider Search

- A plain-text description triggers a semantic (vector) search.
- A structured query with `available_time`, `location`, and `criterions` triggers a hybrid search.
- If provider search results are already cached for the current `FINALIZE` stage, the system must return the cached results and not repeat the search.
- Exception: if the first search returned zero results (e.g. due to stale index data), the next search attempt must perform a real search rather than returning the cached empty list.
- The provider search pipeline in `FINALIZE` consists of four steps:
  1. Structured query extraction: the LLM converts the problem summary into a structured object (`available_time`, `category`, `criterions`).
  2. Hypothetical provider profile generation (HyDE): the LLM writes a description of the ideal provider as a vector query. Steps 1 and 2 run concurrently.
  3. Wide-net hybrid retrieval from the search index using both the HyDE vector and the structured fields, returning up to `min(max_providers × 5, 30)` candidates.
  4. Cross-encoder re-ranking of candidates against the original problem summary to select the final top-N results.
- The HyDE profile is always generated in English, regardless of the session language. It is used solely for vector embedding and is never shown to the user.
- Provider candidates inactive for more than 180 consecutive days (no sign-in) are excluded from all search results.
- Availability-based filtering is applied only when the user's stated `available_time` contains recognised tokens (specific day names, `weekday`, `weekend`, `morning`, `afternoon`, `evening`). If the stated availability uses unrecognised terms (e.g. "flexible", "any time", "next week") that do not map to a known token, no availability filter is applied and all matching providers are returned regardless of availability.
- The "problem summary" used as the basis for provider search is the most recent AI response text. If no AI response has been generated yet, the concatenation of raw user inputs accumulated during `TRIAGE` is used instead.
- **Zero-result diagnostic**: Evaluated immediately by the Backend Orchestrator (see §6.11). When no providers are returned, the system logs the count of competencies with `is_service_provider = True` in the index, to distinguish between a vocabulary mismatch and a missing or stale provider-flag issue.

### 6.3 Tool Execution

- Tools that require specific permissions must not execute without those permissions. A permission failure must be surfaced as a handled error, not a silent skip.
- A tool may signal a stage transition by including a `signal_transition` value in its result. This transition is handled by the conversation stream.

### 6.4 Service Request Linkage

- When a service request is created through the AI assistant, the resulting service request identifier is immediately written to the active AI conversation document. This linkage persists after the session ends.
- **Orphaned Service Requests:** If the linked AI conversation document expires (after 30 days) and is automatically deleted, the service request retains a nullified conversation ID and the chat history simply becomes inaccessible from the request view. The request itself is not deleted.

### 6.5 Simultaneous REST and AI Cancellation

- If a seeker cancels a request via the AI, and simultaneously a provider accepts it via REST API, the system must rely on Firestore transaction locks. The first to commit wins, and the AI must be informed of the state mismatch to gracefully explain the race condition to the user.

### 6.6 Service Request Cancellation via AI

- A service request can be cancelled through the AI conversation (using the cancel intent within the assistant) in addition to direct REST API calls.
- Because service requests are only created at the moment the user accepts a provider (see §6.10), a `FINALIZE → TRIAGE` back-transition due to zero results or user cancellation never requires a cancellation step — no document exists yet at that point.
- The `cancel_service_request` tool remains available for explicit AI-driven cancellation in other scenarios (e.g. user initiates cancellation from `TOOL_EXECUTION` or a post-creation flow). Calling it when no active request exists is a no-op.

### 6.7 HyDE — Hypothetical Document Embeddings

Step 2 of the provider search pipeline generates a short hypothetical provider profile that bridges the vocabulary gap between the user's natural-language request and the terse competency bios stored in the search index.

- The system calls the LLM with the problem summary and instructs it to write a **3–5 sentence prose profile** of a perfect service provider for that request.
- The profile is written in the **third person** (e.g. "This provider is …") and must mention the specific skills, tools, experience, type of work, and any contextual constraints (timing, location, complexity) **using terminology that aligns with the provider enrichment phase**. It reads like a real provider bio, not a checklist.
- The HyDE profile is **always generated in English**, regardless of the session language. It is a vector-search artefact and is never shown to the user.
- When HyDE generation succeeds, the resulting text is used as the Weaviate query string, **overriding** the structured query text from Step 1. Both the vector component (bi-encoder embedding) and the BM25 component of the hybrid search benefit from the richer vocabulary in the hypothetical profile.
- If HyDE generation fails for any reason (exception or empty output), the system falls back silently to the structured query text from Step 1. No error is surfaced to the user.
- Steps 1 and 2 are fired as concurrent async tasks and awaited together, so structured-query extraction and HyDE generation do not block each other.

#### Structured Query Extraction (Step 1 detail)

- The LLM converts the problem summary into a structured JSON object with three fields: `available_time` (free-form time string), `category` (service category), and `criterions` (list of requirement strings).
- The `available_time` field must always be expressed using English time tokens (`monday`–`sunday`, `morning`, `afternoon`, `evening`) or a recognised skip-phrase (`flexible`, `any time`, `anytime`), regardless of the session language. The extraction prompt must enforce this constraint explicitly so that non-English day names (e.g. "Montag") are never produced.
- The last 3 messages from the session's conversation history are appended to the extraction prompt so the LLM has richer context than the summary alone.
- If the LLM returns malformed JSON or an exception is raised, the system falls back to the plain-text problem summary.
- The structured query is combined into a single query string of the form `"<category>. Features: <criterion1>, <criterion2>"` for passing to the BM25 component.

### 6.8 Hybrid Retrieval Parameters

- The search index uses a **hub-spoke schema**: `User` nodes (hub) linked bidirectionally to `Competence` nodes (spokes). The hybrid search targets the `Competence` collection and resolves owning-user properties via the `owned_by` cross-reference.
- Search mode: **hybrid** with `alpha = 0.5` (equal weight for vector similarity and BM25 keyword matching).
- **Boosted query properties**: `title` carries a 2× BM25 boost. The `category`, `description`, `search_optimized_summary`, and `availability_text` fields are searched at standard weight. The `search_optimized_summary` field is the primary source for the vector component.
- **Wide-net fetch**: `min(max_providers × 5, 30)` candidates are retrieved from the index before reranking. This oversampling gives the cross-encoder a diverse pool to score.
- **Ghost filter**: providers inactive for more than 180 days (measured by `last_sign_in`) are excluded from all results. Providers whose `last_sign_in` is null (recorded before activity tracking was introduced) are treated as active and included.
- **Provider flag filter**: only competencies whose owning user has `is_service_provider = True` in the search index are returned.
- **Availability filter**: if the stated `available_time` contains at least one recognised time token (`monday`–`sunday`, `weekday`, `weekend`, `morning`, `afternoon`, `evening`), a filter is applied on `availability_tags`. If the value uses no recognised tokens (e.g. "flexible", "any time", "next week", or an unrecognised free-form phrase), the availability filter is **skipped entirely** — the system does not apply a filter that would silently return zero results.
- **Client-side grouping**: results are grouped by provider. When a user has multiple matching competencies, only the highest-scoring one is retained. The final candidate list contains at most one entry per provider.
- **Zero-result diagnostic**: when no providers are returned, the system logs the count of competencies with `is_service_provider = True` in the index, to distinguish between a vocabulary mismatch and a missing or stale provider-flag issue.

### 6.9 Cross-Encoder Reranking

Step 4 of the provider search pipeline re-scores the wide-net candidates using a cross-encoder that evaluates each (query, document) pair jointly, producing rankings more accurate than the bi-encoder used during retrieval.

- **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2` — a lightweight MiniLM-backbone model trained on the MS MARCO passage-ranking dataset, optimised for matching natural-language queries against descriptive text.
- The model is lazy-loaded on the first reranking request. A single shared instance is used across all concurrent sessions; the model is never constructed multiple times.
- The model is bundled locally in the deployment package. If the bundled file is absent (e.g. before `git lfs pull`), the system downloads it from HuggingFace Hub on first use and logs a warning.
- **Candidate text construction**: each provider candidate is represented as a single string: title (or category if title is absent), then `search_optimized_summary`, then `skills_list` items prefixed with "Skills: ", all joined with ". ". If all fields are empty, the text defaults to "No description available.".
- **Query**: the original plain-language problem summary is used as the cross-encoder query, not the HyDE text or structured query.
- **Execution**: scoring runs in a thread executor to keep the async event loop non-blocking.
- Each returned provider dict is augmented with a `rerank_score` (float) field. Candidates are sorted by `rerank_score` descending; any candidate whose score falls below a configurable minimum relevance threshold is excluded before the list is sliced to `max_providers`. The threshold is deployment-configurable (default −5.0 on the ms-marco model scale) and prevents clearly irrelevant providers from surfacing when the candidate pool is sparse.
- If reranking fails for any reason (exception), the original Weaviate-ordered candidates are returned truncated to `max_providers`, with no error surfaced to the user.
- If no `CrossEncoderService` is available, the Weaviate candidates are simply truncated to `max_providers` without reranking.
- The same reranking step is applied when the `search_providers` tool is called explicitly mid-conversation (outside the `FINALIZE` pipeline), whenever a `CrossEncoderService` is available.

### 6.10 Service Request Creation Semantics

- A service request document is created **only at the moment the user explicitly accepts a provider** (via the `accept_provider` tool in the `FINALIZE` stage). It is never created before that point.
- The service request must be fully populated at creation time. The AI must include all details gathered during `TRIAGE` and `CONFIRMATION`:
  - `title`: a concise label for the job (e.g. "Mobile App Development").
  - `description`: the full scope summary assembled during scoping.
  - `selected_provider_user_id`: the Firebase UID (`user.user_id`) of the accepted provider as returned by the provider search results.
  - `location`: always required — use the city or address provided by the user. If the user provided no location, ask for it before calling `accept_provider`.
  - `category`: the service category as inferred by the AI from the conversation. Must be one of the canonical values (`pets`, `housekeeping`, `restaurant`, `technology`, `gardening`, `electrical`, `plumbing`, `repair`, `teaching`, `transport`, `childcare`, `wellness`, `events`, `other`). Always required — use `other` if no specific category can be determined.
  - `start_date` / `end_date`: concrete calendar dates if the user stated a timeframe; omitted otherwise. The client must display a safe fallback when `start_date` is absent.
  - `amount_value`: the user's stated budget figure, if provided. The client must display a safe fallback (e.g. 0) when absent.
  - `currency`: derived from the service `location` (Germany, Austria, Switzerland → `EUR`; UK → `GBP`; US → `USD`). Omitted if location is unknown or ambiguous. Never asked from the user.
  - `requested_competencies`: list of specific skills or competencies mentioned during scoping.
- Simultaneously with the service request creation, the backend records the accepted provider as a **provider candidate** entry linked to that service request. The candidate entry carries the provider's ranking score (normalised to a 0–100 range) and the matched competency label as scoring reasons. Only the accepted provider is stored this way — providers shown but not selected during the `FINALIZE` loop are not persisted as candidates.
- If the user refuses every presented provider — either by exhausting the candidate list via `reject_and_fetch_next` or by explicitly cancelling via `cancel_search` — the system returns to `TRIAGE` and **no service request is created**.
- If the provider search returns zero results, the `FINALIZE` stage is bypassed entirely and **no service request is created**.
- Because the service request is only created on acceptance, a `FINALIZE → TRIAGE` back-transition (zero results or user cancellation) requires no cancellation step — no document exists at that point.
- The `CONFIRMATION` stage summary must include location, timeframe, and budget **only when the user provided them**; it must not invent or approximate values that were not stated.

### 6.12 Google Places External Provider Search

> **This section applies exclusively to lite mode (`AGENT_MODE=lite`).** In full mode, Google Places is never queried and none of the behaviours below are active.

This section defines the behaviour of the external provider search mode backed by the Google Places API. In lite mode, this integration is always active.

#### 6.12.1 Configuration

- In lite mode, Google Places external search is always active. There is no per-instance flag to toggle it; enabling or disabling it is done by switching the agent mode.
- The Google Places API key is provided via a server-side secret and must never be exposed to the client.

#### 6.12.2 Query Construction

- Immediately after the user confirms the scoped request in `CONFIRMATION`, the system constructs a single Google Places search query derived from the confirmed MRI fields.
- The LLM automatically derives this query: it analyses the confirmed service requirements and generates one natural-language search phrase that captures the core intent and the user's location (e.g. `"DJ for wedding Munich"`, `"wedding photographer Munich"`).
- The user's confirmed location (which is a hard MRI requirement when Google Places is enabled) is appended to the query as a geographic anchor.
- The user is not asked to review or confirm the generated query. The LLM derives it autonomously from the MRI context.
- Multi-category requests (e.g. a wedding requiring DJ, photographer, and venue) are expressed as a single broad query in the current version. Support for multiple sub-queries per service category is deferred to a future iteration.

#### 6.12.3 Transparency

- When the Google Places search is initiated, the system must inform the user transparently that an external Google Maps search is being performed in addition to the internal search (e.g. "I am also searching Google Maps for providers near you — this may take a moment.").
- This announcement is made once per `FINALIZE` entry, before the first results are presented. It must not be repeated for subsequent turns within the same `FINALIZE` session.

#### 6.12.4 Fetching and Storage

- Google Places queries are executed concurrently. The system does not cache Google Places results between sessions: every `FINALIZE` entry triggers a fresh fetch from the Google Places API.
- Each result returned from Google Places is normalised into the platform's canonical provider record format. The normalised record must include at minimum: name, address, phone number (if available), website (if available), Google rating (if available), geographic coordinates, and a source tag identifying the record as originating from Google Places.
- Immediately after fetching and normalisation, all Google Places results are written to the internal search index (Weaviate) using the same schema as registered platform providers, so they participate in the unified vector and hybrid ranking pipeline.
- Because Google Places providers are not registered platform users, they must be written to the search index with a distinct source flag (e.g. `source: "google_places"`) and must never be assigned a platform user ID or trigger any user-account-related operations (e.g. provider pitch eligibility checks).

#### 6.12.5 Unified Ranking

- Once both the Google Places results and the internal Weaviate results have been fetched (or one source has failed gracefully), all candidates are merged into a single pool.
- The existing ranking pipeline (HyDE + hybrid retrieval + cross-encoder reranking, §6.7–§6.9) is applied to the unified pool. The final ranked list is a single unified list ordered by relevance score; results are not grouped or separated by source.
- The maximum number of providers presented to the user (`max_providers`) applies to the unified list.

#### 6.12.6 Failure and Degradation

- If the Google Places API is unreachable, returns an HTTP error, or times out, the system must log the error and proceed using only the internal search index results.
- In this case, the system must inform the user once that the external search was unavailable and that results are sourced from the internal index only.
- A Google Places API failure must never trigger a transition to `RECOVERY`; it is a recoverable partial failure, not a total search failure.
- If both the Google Places API and the internal search index return zero results, the standard zero-result handling applies (§6.11 Phase 1: `FINALIZE` is bypassed and the FSM transitions back to `TRIAGE`).

#### 6.12.7 Contact Template Generation

- For each provider presented in `FINALIZE` (whether sourced from Google Places or the internal index), the system must be capable of generating a ready-to-send contact email or message template on explicit user request (e.g. "Can you write me a message to send to them?").
- The template must be personalised to the user's confirmed scoped request and addressed to the specific provider by name.
- Template generation is never triggered automatically; it only fires when the user explicitly requests it. The LLM calls the `generate_contact_template()` tool to signal this intent; the orchestrator injects the provider's contact details and request summary so the LLM generates the template in the follow-up turn.
- The template is delivered as a text message in the conversation, formatted for easy copy-paste.
- The LLM must not announce or narrate the tool call before generating the template — the follow-up response is the template itself.

#### 6.12.8 Provider Pitch Eligibility

- The standard `PROVIDER_PITCH` / `PROVIDER_ONBOARDING` flow (§4) applies unchanged in sessions that use Google Places. The presence of externally sourced results does not suppress or modify the pitch eligibility check.
- Google Places provider records written to the search index must not be counted as registered platform providers for the purposes of any pitch-eligibility or provider-count logic.

---

### 6.11 FINALIZE Stage Multi-Turn Interaction (Smart Backend & Tool-Driven FSM)

To prevent the LLM from drifting or failing to emit generic stage transitions, the `FINALIZE` loop relies on **Backend Pre-Routing** and **State-Mutating Tools**. The LLM inside `FINALIZE` does not possess the `signal_transition` tool; the stage transitions are side-effects of concrete tool execution managed by the orchestrator.

#### Phase 1: Backend Pre-Routing (Entry Check)
When the provider search completes, the Backend Orchestrator intercepts the payload *before* invoking the `FINALIZE` LLM:

* **If `results == 0`**: 
  The Backend completely bypasses the `FINALIZE` LLM. It forcefully transitions the FSM back to `TRIAGE` and passes a silent system event to the `TRIAGE` LLM: `[System Event: The provider search returned 0 results. Apologise to the user and ask how they would like to broaden their criteria.]`
* **If `results > 0`**:
  The Backend caches the full result list, sets the FSM to `FINALIZE`, and passes *only* the top result (`results[0]`) into the LLM prompt with instructions to present this provider and wait for the user's decision.

#### Phase 2: Tool-Driven Interaction (The Loop)
The `FINALIZE` LLM is equipped with exactly four functional tools: `accept_provider(provider_id)`, `reject_and_fetch_next()`, `cancel_search()`, and `generate_contact_template()`.

- **User Response A: Decline current, ask for another**:
  - The user rejects the suggestion ("No, someone else", "Too expensive").
  - The LLM evaluates the intent and calls the `reject_and_fetch_next()` tool.
  - *Orchestrator Action*: The backend executes the tool, pops the next candidate from the cached list, injects it into the context, and leaves the state in `FINALIZE`. If the cached list is empty, the orchestrator automatically transitions the state to `TRIAGE` and prompts the LLM to inform the user.

- **User Response B: Ask for more detail about the current result**:
  - The user asks a specific question ("What are their exact hours?", "Do they speak German?").
  - The LLM answers naturally based on the current provider's injected profile. **No tool is called.**
  - *Orchestrator Action*: The FSM safely remains in `FINALIZE`, waiting for the user to make a final decision on this provider.

- **User Response C: Accept current result**:
  - The user explicitly accepts the current provider ("Yes, let's go with him").
  - The LLM evaluates the intent and calls `accept_provider(provider_id)`.
  - *Orchestrator Action*: If the selected provider is sourced from Google Places (i.e. not a registered platform user), the backend must not create a service request. Instead, it returns an error payload with the provider's contact details (phone, website, address) and the LLM must explain that the provider cannot be booked directly on Linkora but provides their contact information for the user to reach out independently.
  - If the provider is a registered platform user, the backend executes the tool, creates the service request document (see §6.10), records the accepted provider as a `provider_candidate` sub-document with their normalised ranking score, and **automatically forces the state transition** to `COMPLETED`. No service request or candidate document is written for any provider the user did not accept.

- **User Response D: Cancel the request**:
  - The user aborts the flow entirely ("Nevermind", "Cancel the search").
  - The LLM evaluates the intent and calls `cancel_search()`.
  - *Orchestrator Action*: The backend forces the state transition to `TRIAGE` to clear the scoping draft.

- **User Response E: Referencing a previously presented result**:
  - If the user decides to select a provider presented earlier in the loop ("Let's go back to the first guy"), the LLM (using the chat history context) calls `accept_provider(provider_id)` with the older ID.
  - *Orchestrator Action*: Proceeds as **Response C**.

- **User Response F: Disconnection**:
  - If the user drops connection while in `FINALIZE`, background search tasks are aborted. 
  - Session resumption rules (§9.2) apply on reconnect.

---

## 7. Client–Server Communication Protocol

### 7.1 Message Format

| Direction       | Message Structure                                                                           |
|-----------------|---------------------------------------------------------------------------------------------|
| Client → Server | `{"type": "text-input", "text": "…"}`                                                      |
| Client → Server | `{"type": "mode-switch", "mode": "text" | "voice"}`                                        |
| Server → Client | `{"type": "chat", "text": "…", "isUser": bool, "isChunk": bool}`                           |
| Server → Client | `{"type": "runtime-state", "runtimeState": "<state>"}` — current agent runtime FSM state  |

- `isChunk: true` means the message is a streaming fragment. The client must accumulate all fragments before treating the message as complete and displaying it.
- The server emits a `runtime-state` message both when the DataChannel is first attached and again when it is confirmed open, so the client receives the correct state even if it connects after the FSM has already advanced.
- The client maps incoming runtime-state values to UI conversation states: `bootstrap` / `data_channel_wait` → connecting; `thinking` / `llm_streaming` / `tool_executing` → processing; `listening` / `speaking` / `interrupting` / `mode_switch` → listening; `error_retryable` / `terminated` → idle. Unknown state values are silently ignored.
- Text-input messages exceeding 10,000 characters are rejected by the server with a warning and are not processed.
- **Maximum Utterance Duration**: In voice mode, the server must cap continuous user audio input at 60 seconds. If the user speaks without pausing for 60 seconds, the system should force-finalize the transcript and process the chunk to prevent memory exhaustion.

### 7.2 Connection Readiness Guard

- The client must not send messages over the network before the data channel is fully open.
- Messages that arrive while the UI is in a dormant state (post-timeout) or before the channel is ready must be buffered and sent immediately once the background connection opens.

### 7.3 Mode Switching Within a Session

- Switching from voice to text mode within an active session does not require a new WebRTC connection. The client mutes the microphone and sends a `mode-switch: text` event, which causes the server to immediately interrupt any in-progress TTS output.
- Switching from text to voice mode acquires microphone permission and renegotiates the existing WebRTC connection to add an audio track. If microphone permission is denied, the switch fails silently and the session remains in text mode.
- If a voice track already exists but is muted (from a previous downgrade to text mode), switching back to voice unmutes the track and sends `mode-switch: voice` — no renegotiation is required.
- If a new audio track arrives on an existing voice session (e.g. Bluetooth device swap), the system replaces the input track and restarts the audio sub-tasks without resetting conversation state.
- If a text-to-voice upgrade is triggered but the audio track does not arrive within 5 seconds after the offer, the upgrade fails. The client must automatically revert the UI to text mode so the user is not left in a broken intermediate state.

### 7.4 Client-Side Idle Timeout (Dormant UI State)

- The client automatically terminates an active WebRTC/WebSocket connection after 10 consecutive minutes of inactivity (no incoming messages of any type) to save device resources and server connections. 
- On timeout, the network session is torn down, **and the visual chat history is cleared.** The UI returns to its default idle/start state.
- If the user interacts again, it initiates a completely new session connection.

### 7.5 Optimistic Message Display

- When a user submits a text message, the client adds it to the chat view immediately, before the server confirms receipt. If the server subsequently echoes the same message, the client must detect and discard the duplicate by maintaining a FIFO queue of pending optimistic message texts. The first queue entry whose text matches the incoming echo is dequeued and the echo is suppressed; if no queue entry matches, the message is displayed normally. This FIFO approach correctly handles rapid-succession sends where the same text could be sent twice, ensuring genuine repetitions (e.g., 'Hello?') are not falsely deduplicated. Additionally, the server FSM must ensure that if the user's first message contains a standard greeting, the LLM does not double-greet if an autonomous system greeting was already dispatched (or vice versa, as greetings are now dynamically driven by the LLM).

### 7.6 Microphone Mute Lifecycle

- In voice mode, the microphone starts muted at session initiation and is unmuted only once the DataChannel is confirmed open.
- The microphone is also unmuted each time the AI begins a new response, so the user can speak to interrupt.
- In text mode, the microphone remains muted for the entire session duration.

### 7.7 Connection Failure Handling

- If the WebRTC peer connection experiences network disruption, there is a short grace period (e.g., 5 seconds) allowing for ICE restarts or reconnection (e.g. Wi-Fi to Cellular handoff).
- If the peer connection reaches a failed, disconnected, or closed state and the grace period expires, or the WebSocket signaling channel closes or errors while a session is active, the client automatically tears down the session and returns the UI to its idle state.
- If a session start fails for any reason (microphone permission denied, server unreachable, or any other error), the UI returns to idle, the mode is reset, the pending message buffer is cleared, and an error is made available for display.
- If a session start is already in progress, any subsequent start request must be silently ignored until the in-flight start completes or fails.
- The WebSocket connection URL must include the authenticated user's identifier as a query parameter. If no authenticated user is present, the connection attempt must fail immediately before any network call is made.

### 7.8 Audio Device Change During Voice Session

- When an audio input device change is detected during a live voice session, the client must automatically recreate the audio track from the new device and renegotiate the peer connection, preserving the previous mute state. If a renegotiation is already in progress when the device change fires, the device change is deferred until the current renegotiation completes.

---

## 8. REST API Behaviour

- All REST endpoints require a valid authentication token (Firebase Bearer).
- Write operations go to Firestore first; the search index is updated subsequently.
- The login sync endpoint must be idempotent — repeated calls with the same user data must not degrade or corrupt existing data.

### 8.1 Login Sync Field Update Rules

- The login sync endpoint updates `email` and `last_sign_in` unconditionally for existing users.
- `name` and `photo_url` are updated only when the incoming values are non-empty (to handle a race where the identity-provider profile has not fully resolved).
- `fcm_token` is updated only when the incoming value is non-empty (to prevent overwriting an existing token with a blank value).
- `is_service_provider` is never accepted from the client body; the authoritative value is always read from the data store before any search-index write.

### 8.2 Sign-In Verification

- The sign-in endpoint verifies the identity token (including revocation check) and returns `user_id`, `email`, and `name`. It does not create or modify any backend data; it is a pure token verification endpoint.

### 8.3 Logout

- The logout endpoint accepts a `user_id` and returns a success status. It performs no backend state changes (no session invalidation, no data-store writes).

### 8.4 User Settings

- The settings read endpoint returns `language` (validated to `"en"` or `"de"`; falls back to `"en"` if the stored value is invalid) and `notifications_enabled` (validated to boolean; falls back to `true` if invalid).
- The settings update endpoint rejects any `language` value that is not `"en"` or `"de"` with HTTP 400. Settings are merged with existing values; unknown keys are ignored. Note that updating the language via REST will not affect any currently active WebSocket sessions; the new language will apply on the next session initialization.

### 8.5 Service Request Permissions and Status Transitions

- Only the seeker (creator) of a service request may update or delete it via the REST API. Any other authenticated user receives HTTP 403.
- Service request status transitions are enforced server-side with role-based rules:
  - A provider may move a request from `pending` or `waitingForAnswer` to `accepted` or `rejected`, and from `accepted` to `serviceProvided`. A provider who has lost their global "provider" status (e.g. deleted all competencies) retains permission to transition their existing accepted requests to `serviceProvided`.
  - A seeker may move a request from `pending`, `waitingForAnswer`, or `accepted` to `cancelled`, and from `serviceProvided` to `completed`.
  - A user who is neither the seeker nor the selected provider is forbidden from any status change.
  - Any other transition is rejected with HTTP 422.

### 8.6 Push Notifications on Service Request Events

- When a service request is created, a push notification is sent asynchronously to the selected provider. This is fire-and-forget and does not block the API response.
- When a service request's status changes, push notifications are sent asynchronously to both the seeker and the provider, identifying who made the change.

### 8.7 Competence Creation via REST

- When a competence is created via the REST API, the system triggers an LLM enrichment step that extracts `skills_list`, `search_optimized_summary`, `price_per_hour`, `availability_tags`, `availability_text`, and `category` from the raw data. These enriched fields are written back to the data store and synced to the search index.
- Enrichment failure is non-fatal; the competence is still created. In this case, the raw description is indexed into Weaviate as a fallback, and default empty tags are applied to ensure the competence remains searchable.
- Creating any competence via the REST API immediately sets `is_service_provider = True` on the user in both the data store and the search index.
- If the user's search-index node is missing at the time of competence creation, it is self-healed by recreating it from authoritative data before the new competence is synced.

### 8.8 Reviews

- Review ratings must be between 1 and 5 inclusive.
- The reviews list endpoint requires at least one filter parameter (`user_id`, `reviewer_id`, or `service_request_id`). If no filter is provided, an empty list is returned.
- **Review Permissions**: A user may only submit a review for a service request if they are the original seeker or the matched provider, and only if the service request has reached the `serviceProvided` or `completed` status.
- **Counterparty Constraint**: When submitting a review, the `user_id` of the reviewed party must be the opposing counterparty of the service request. If the reviewer is the seeker, only the matched provider may be reviewed; if the reviewer is the matched provider, only the seeker may be reviewed. Any attempt to review oneself or a third party must be rejected with HTTP 403.

---

## 9. Connection Lifecycle

- Each WebRTC connection has a 10-minute server-side idle timer. If no user activity (voice transcript finalisation, text input, or mode switch) is detected within this window, the connection is automatically closed and all associated resources are released.
- The idle timer is reset on every user activity event. Empty audio chunks or audio classified purely as background noise by the VAD (Voice Activity Detection) must not reset the 10-minute idle timer. Specifically, an empty or whitespace-only STT transcript must not count as user activity and must not reset the idle timer.
- When a connection is closed (intentional or timeout), the current conversation stage and the active request summary (if any) are written to the AI conversation document in Firestore, and the runtime state machine is transitioned to its terminal state.
- An invalid `mode` query parameter (any value other than `"voice"` or `"text"`) on a WebSocket connection is silently coerced to `"text"` to prevent unintended audio playback in inappropriate environments.

### 9.1 Runtime FSM Bootstrap Sequence

- When a new session is established, the server-side agent runtime FSM is initialised in the `BOOTSTRAP` state.
- The FSM advances to `DATA_CHANNEL_WAIT` as soon as the WebRTC peer connection is negotiated and the data channel attachment is confirmed.
- Once the data channel is confirmed open, the FSM invokes the **Session Resumption (State-Aware Hydration)** check (see §9.2) to determine whether to restore previous context or start fresh, and then transitions to the appropriate state (e.g., `LISTENING`, `GREETING`, or `TRIAGE`).
- The current FSM state is emitted as a `runtime-state` message on both the initial data-channel attachment and again when the channel open event fires, ensuring the client always receives the correct state even if it connects after the FSM has already advanced past `BOOTSTRAP`.
- **Text-mode initialization race guard**: After the FSM advances to `LISTENING`, a text-mode session applies a brief wait (up to 300 ms) before committing to an autonomous greeting. If the client delivers a text message within this window (e.g., a buffered message sent immediately after the DataChannel opens), the system skips the standalone greeting and transitions directly to `TRIAGE`, allowing the LLM to process greeting and user intent in a single combined turn. If no message arrives within 300 ms, the autonomous greeting is generated and dispatched normally.
- **FSM stuck-state prevention**: The `stream_complete_text` event must be emitted unconditionally at the end of every LLM response pipeline turn — whether the stream yielded text, yielded only tool-calls (no text), or raised an exception. The FSM must accept `stream_complete_text` from both `THINKING` and `TOOL_EXECUTING` states (in addition to `LLM_STREAMING`) and transition to `LISTENING`. This ensures the FSM is never permanently stuck when the LLM produces a pure function-call response with no accompanying text fragments.

### 9.2 Session Resumption (State-Aware Hydration)

To ensure conversations feel natural across disconnects and timeouts, the system dynamically restores context based on the user's last known task state and explicit intent upon reconnection.

When a new connection is established, the server must check Firestore for the user's most recent AI conversation document (restricted to the last 24 hours). 

1. **Context Injection:** Regardless of how the last session ended, the system silently injects a lightweight summary of the previous session's final state (including the scoped request draft and final stage) into the LLM's initial system prompt (e.g., `[System Context: The user's previous session ended 15 minutes ago. Last discussed request: "Fixing a leaking pipe in the kitchen".]`).
2. **Explicit Continuation:** If the user initiates the new session by explicitly asking to continue their last request (e.g., "Let's continue with the plumber search" or "Where were we?"), the AI uses the injected context to summarize the last known state to the user in 1-2 sentences and restores the previous request data into the active session memory. The FSM is then transitioned to the appropriate active stage (e.g., `TRIAGE` or `CONFIRMATION`) to resume the flow.
3. **Fresh Start (Clean Break):** If the previous session ended in a terminal state (`COMPLETED`, `FINALIZE`, `PROVIDER_PITCH`, `PROVIDER_ONBOARDING`) and the user's new message introduces a *new* intent (or they simply say "Hello"), the AI ignores the previous context, leaves the FSM in the new session state, and boots into the standard `GREETING` or `TRIAGE` flow. 
4. **Unfinished Business (Auto-Resume):** If the last session abruptly dropped mid-flow (e.g., during `TRIAGE`, `CLARIFY`, or `CONFIRMATION`), the system automatically restores the in-memory request draft and resumes the FSM at that exact stage, prompting the AI to naturally welcome the user back and acknowledge the interrupted task.

### 9.3 Client-Side Connection Resilience

- When the WebRTC peer connection enters a transient `Disconnected` state (e.g., a brief network hiccup), the client waits up to 5 seconds for the connection to recover before triggering a full disconnect sequence. If the connection recovers to `Connected` within this grace period, the session continues uninterrupted. If the connection transitions to `Failed` or `Closed`, the client disconnects immediately without waiting.
- When the user sends a text-mode message, the client displays it immediately in the chat history (optimistic UI). If the server subsequently echoes back the same message text as a user message over the DataChannel, the client suppresses the duplicate and does not add it a second time. If the server sends a user message with different text, it is shown normally.

---

## 10. Voice Output Pipeline

- TTS synthesis runs per sentence. Multiple sentences are synthesised concurrently; however, audio chunks are played back in the order they appear in the LLM stream, regardless of which sentence finishes synthesis first.
- Sentences shorter than 15 characters are merged with the next sentence before being sent for TTS synthesis, to avoid overly short, choppy audio segments.
- **End-of-Stream (EOF) Flush for Short Sentences:** Because sentences shorter than 15 characters are merged with the next, an EOF marker from the LLM stream must immediately force the synthesis and playback of the buffer, even if it contains fewer than 15 characters (e.g., "Thank you.").
- **No Punctuation Timeout:** To handle cases where the LLM generates long text blocks without valid punctuation marks, a hard character limit fallback is applied: if no punctuation is detected within 200 characters, the sentence buffer is forcefully split at the nearest space to ensure streaming audio is not indefinitely blocked.
- Each audio chunk has a cosine fade-in (10 ms) and fade-out (3 ms) applied to prevent audible click or crackle artefacts.
- TTS playback waits at most 30 seconds for all pending sentence synthesis tasks to complete. If the timeout is exceeded, remaining unplayed chunks are silently abandoned and the pipeline proceeds.

---

## 11. Search Index Enrichment

- When provider competency descriptions are written to the search index, the category name is expanded with a set of related parent terms (e.g. "Electrical" expands to include "Electrician", "Lighting", "Wiring", "Power"). This improves recall for broad searches.
- Availability data for a provider is converted to filter tokens before being written to the search index: individual day names, aggregate tokens (`weekday`, `weekend`), time-of-day tokens (`morning`, `afternoon`, `evening` derived from HH:MM time ranges), and absence tokens for blocked days.

---

## 12. Health Endpoint

- The server exposes a health endpoint that returns `{"status": "healthy", "active_connections": N}`. This endpoint does not require authentication.

---

## 13. Edge Cases & Invariants

- The system must never hardcode a language string. Language must flow from the session parameter through every layer of processing. This invariant applies to **all** user-visible output paths without exception, including LLM error fallback messages (e.g. when the LLM fails to generate a response) and greeting fallback strings generated when the LLM call fails during session initialisation. There is no user-facing string that is exempt from this rule.
- Text-mode sessions must never attempt to play audio or synthesize a spoken greeting. However, they must still dispatch the initial text greeting as defined in the flow.
- If the AI is speaking and new input arrives, the current speech output must be interrupted before processing the new input. The interrupted state must be handled gracefully with no orphaned history entries.
- The permanent opt-out sentinel for the provider pitch must be treated as a special value — never as a real date — throughout all date comparisons.
- Search input is capped at 20 unique words before being written to the search index to prevent embedding noise. While search input is capped at 20 unique words, it must also be capped at a maximum character length (e.g., 200 characters), truncating gracefully at the nearest word boundary to prevent a malicious user from submitting a single 10,000-character string without spaces to overload the embedding model and prevent accidental string corruption.
- **Android Echo Cancellation (AEC)**: On Android, hardware echo cancellation requires the audio subsystem to be in communication mode. This mode must be set every time audio is routed to a speaker or Bluetooth device — both at session start and on every routing change. It must be active regardless of build configuration (development, staging, production) and must not be conditionally skipped for any reason such as debug mode.
- **Speaking-flag lifetime**: The AI speaking state must remain active until the buffered audio output has finished playing — not merely until audio data has been queued. If the speaking state is cleared while audio is still buffered, subsequent voice input will be misclassified as user speech.
- **Post-interrupt echo suppression**: When voice input arrives while the AI is speaking and triggers an interruption, the final transcript of that triggering utterance must be discarded and must not be forwarded to the AI as user input. Only voice input that arrives after the interruption has completed may be treated as a new user turn.

---

## 14. Agent Mode Configuration

### 14.1 Mode Selection

- The active agent mode is set by the server-side configuration parameter `AGENT_MODE`.
- Valid values: `full` (default) and `lite`.
- The mode applies for the lifetime of the server process and cannot be changed per-session.
- If `AGENT_MODE` is set to an unrecognised value, the system must log a warning and operate in `full` mode.
- At startup, the server must log the active agent mode before accepting any connections (e.g. `AGENT_MODE=lite active`).

### 14.2 Feature Comparison

The table below provides a complete at-a-glance overview of which features are active in each mode. Detailed rules follow in the per-mode sections.

| Feature | `full` | `lite` |
|---|---|---|
| Active conversation stages | GREETING, TRIAGE, CLARIFY, CONFIRMATION, TOOL_EXECUTION, FINALIZE, RECOVERY, COMPLETED, PROVIDER_PITCH, PROVIDER_ONBOARDING | GREETING, TRIAGE, CLARIFY, CONFIRMATION, FINALIZE, RECOVERY, COMPLETED |
| Voice (STT / TTS / WebRTC audio) | Yes | No — text only |
| Google Places external search | Not used — internal search index only | Always active |
| FINALIZE: user selects a provider | Yes — multi-turn, user accepts or rejects | No — results presented as list, auto-advance to COMPLETED |
| Service request creation | Yes | No |
| Favorites retrieval | Yes | No |
| Open service request retrieval | Yes | No |
| Provider pitch (30-day cycle) | Yes | No |
| Provider onboarding | Yes | No |
| MRI: contextual details (min. 3) | Required | Required |
| MRI: location | Required when GP enabled; soft-ask otherwise | Always required |
| Soft-asks (budget, etc.) | Yes | Yes |
| Chat message persistence | Yes (30-day TTL) | Yes (30-day TTL) |

### 14.3 Full Mode

- `full` is the default mode. It corresponds to the complete conversation behaviour described in all other sections of this specification.
- No behaviour from any section is skipped or modified in `full` mode.
- Google Places is never instantiated, queried, or referenced in full mode, regardless of whether a `GOOGLE_PLACES_API_KEY` is present in the environment. Provider discovery uses only the internal search index.

### 14.4 Lite Mode

Lite mode provides a simplified conversation experience optimised for fast, Google Places-backed provider discovery with minimal friction.

#### Stages and Transitions

The GREETING, TRIAGE, CLARIFY, CONFIRMATION, FINALIZE, COMPLETED, and RECOVERY stages are active. The TOOL_EXECUTION, PROVIDER_PITCH, and PROVIDER_ONBOARDING stages are not accessible in lite mode; any transition targeting them is treated as an illegal transition and silently ignored.

| Current Stage | Allowed Next Stages |
|---|---|
| `GREETING` | `TRIAGE` |
| `TRIAGE` | `CONFIRMATION`, `CLARIFY`, `RECOVERY` |
| `CLARIFY` | `TRIAGE` |
| `CONFIRMATION` | `FINALIZE`, `TRIAGE` |
| `FINALIZE` | `COMPLETED`, `RECOVERY`, `TRIAGE` |
| `COMPLETED` | `TRIAGE` |
| `RECOVERY` | `TRIAGE` |

#### Minimum Required Information (MRI)

In lite mode, the AI must collect the same MRI as in full mode before it is permitted to advance to CONFIRMATION:

- **Core intent** — the primary service required.
- **Contextual details (minimum 3)** — at least three specific details defining the scope.
- **Availability or urgency** — preferred time slot or urgency level.

In addition, **location is always a hard MRI requirement** in lite mode (not a soft-ask), because the Google Places pipeline requires a geographic anchor for every search.

Soft-asks (budget, exact date resolution) apply exactly as in full mode. The User Override Exception from §3.4 still applies: if the user explicitly refuses further detail, the AI proceeds immediately.

The table below compares MRI requirements across modes:

| MRI Element | Full Mode | Lite Mode |
|---|---|---|
| Core intent (service type) | Required | Required |
| Contextual details (minimum 3) | Required | Required |
| Availability or urgency | Required | Required |
| Location | Required when GP enabled; soft-ask for in-person services otherwise | Always required |
| Budget (soft-ask) | Asked once if clearly relevant | Asked once if clearly relevant |
| Exact dates | Resolved internally; user not asked to re-state as ISO date | Same |
| Soft-asks in general | Yes | Yes |

#### FINALIZE Behaviour

- The GP-backed provider search runs on entry to FINALIZE (identical pipeline to full mode: GP query generation → GP fetch → Weaviate upsert → Weaviate hybrid search).
- After presenting the results to the user as a list, the system automatically advances to COMPLETED. The user is not asked to accept or reject a specific provider. No service request is created in Firestore.
- If the search returns zero results, the system transitions to TRIAGE (not COMPLETED), informing the user that no match was found and inviting them to refine their request.

#### Provider Pitch

The provider pitch eligibility check that normally fires when COMPLETED is reached does not apply in lite mode. COMPLETED always transitions to TRIAGE if the user indicates a new need, and to session end otherwise.

#### Available Tools

The table below lists all registered tools and their availability per mode. Tools marked as unavailable in lite mode must not be dispatched; any LLM attempt to call them must be rejected with a permission error, identical to an insufficient `ToolCapability` error.

| Tool | Full Mode | Lite Mode | Notes |
|---|---|---|---|
| `search_providers` | ✓ | ✓ | GP-backed in lite (always active) |
| `get_favorites` | ✓ | ✗ | Not applicable in lite |
| `get_open_requests` | ✓ | ✗ | Not applicable in lite |
| `create_service_request` | ✓ | ✗ | No service requests in lite |
| `record_provider_interest` | ✓ | ✗ | No provider pitch/onboarding in lite |
| `get_my_competencies` | ✓ | ✗ | No provider onboarding in lite |
| `save_competence_batch` | ✓ | ✗ | No provider onboarding in lite |
| `delete_competences` | ✓ | ✗ | No provider onboarding in lite |

#### Stage Behaviour Summary

The table below describes how each active stage behaves differently in lite mode compared to full mode. Stages not listed behave identically in both modes.

| Stage | Full Mode | Lite Mode |
|---|---|---|
| `TRIAGE` | Collects core intent + minimum 3 contextual details + availability + location (when GP enabled) + optional soft-asks | Identical to full mode, with location always a hard MRI requirement (not a soft-ask). |
| `CONFIRMATION` | 2–3 sentence summary of the fully scoped request including all MRI fields | Identical to full mode. |
| `FINALIZE` | Multi-turn: presents providers, waits for user to accept or reject; user can cancel search; service request written to Firestore on acceptance | Single-turn: presents GP results as a numbered list, then immediately and automatically transitions to COMPLETED; no user acceptance step; no Firestore write |
| `COMPLETED` | Triggers provider pitch when user is eligible; asks if user needs anything else | No provider pitch; simply asks if the user needs anything else |

#### Google Places

Google Places external search is always active in lite mode, regardless of any GP-specific flag. If the Google Places API key is absent or the service is unreachable, lite mode degrades gracefully: the user is informed, and the search falls back to the internal Weaviate index only.

In lite mode, the final provider result set that is presented to the user must contain **only** providers sourced from the Google Places API (identified by their `source` attribute). Providers registered on the platform (internal Weaviate users) must not appear in the results. This source restriction is applied after the unified Weaviate retrieval and reranking pass, immediately before the results are presented to the LLM and user.

The one exception to this source restriction is the degradation path: when the Google Places pipeline fails (the API is unreachable, times out, or returns an error), the source filter is bypassed and the full internal Weaviate result set is used instead. In this case the user must be informed that the external search was temporarily unavailable and that results come from registered providers only.

#### Text-Only Constraint

Lite mode is strictly text-based. The following are prohibited in lite mode:

- Accepting microphone audio or WebRTC voice tracks from clients.
- Running the speech-to-text pipeline (STT / gRPC audio stream).
- Synthesising or streaming text-to-speech audio output (TTS).
- Playing or queuing any audio in the output pipeline.

If a client attempts to establish a lite-mode session with `?mode=voice`, the server must reject the combination, log a warning, and either refuse the connection or silently downgrade to text mode. A lite-mode server must not accept voice sessions under any circumstance.

Because audio is absent, the lite-mode session always behaves as a text session: `skip_greeting` audio is implicit, no spoken greeting is synthesised, and the initial text greeting is dispatched over the DataChannel exactly as described in §3.1 for text mode.

#### Chat Message Persistence

AI conversation messages are persisted to Firestore in lite mode, using the same 30-day TTL rules as full mode.

### 14.5 Invariants Shared Across Both Modes

- The low-level transport and audio state machine (BOOTSTRAP → DATA_CHANNEL_WAIT → LISTENING → THINKING → LLM_STREAMING → TOOL_EXECUTING → SPEAKING → INTERRUPTING → MODE_SWITCH → ERROR_RETRYABLE → TERMINATED) operates identically in both modes. In lite mode, the states SPEAKING and INTERRUPTING are not reachable in practice because no audio output is produced.
- Lite mode supports text session sub-mode only. Full mode supports both voice and text sub-modes.
- Streaming delivery and the DataChannel protocol behave identically in both modes.
- Interrupt handling for text input (arriving while the LLM is streaming) applies in both modes. Voice interrupt handling is not applicable in lite mode.
- Language enforcement (§3.1) applies in both modes without exception.
- The single-acknowledgement rule and silent fast-path transition rules (§3.7, §3.8) apply in both modes.