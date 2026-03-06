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

---

## 3. Conversation Flow

### 3.1 Session Start

- **Voice mode**: the AI greets the user by his name immediately upon connection.
- **Text mode**: The AI starts in the `GREETING` stage just like Voice mode, dispatches the text greeting immediately on page load, and then autonomously transitions to `TRIAGE`.
- **Language Enforcement**: If the WebSocket connection lacks a `language` parameter or provides an invalid one, the system defaults to the user's REST-stored settings language, or `"en"` if none exists. The language parameter provided by the client strictly overrides the REST-stored user setting for the duration of that session. The conversation language cannot be changed mid-session.
- **Unsupported Client Language**: If the client requests a language via WebSocket that the LLM is not localized or tested for (e.g., passing a rare dialect code), the system must fallback to English (`"en"`) and inform the user of the fallback in the first turn.
- **Cross-Lingual Handling**: The AI prompt must strictly enforce that all responses remain in the session-defined language. If the user speaks in a different language, the AI must explicitly translate or acknowledge the input in the configured system language (e.g., "I see you're speaking German, but I am configured for English right now. How can I help?").

### 3.2 Conversation Stages

The conversation progresses through a finite set of named stages. Each stage represents a distinct phase of the dialogue with its own prompt behaviour and transition rules.

| Stage                 | Purpose                                                                                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `GREETING`            | **Welcome.** The AI greets the user by name and checks whether they have an open service request, then invites them to share their need.                      |
| `TRIAGE`              | **Scoping.** The AI acts as a service coordinator: it asks focused questions to understand the user's need just well enough to find a matching provider. It also detects provider-management intent and routes accordingly. |
| `CLARIFY`             | **Disambiguation.** Used when the request is too ambiguous to scope. The AI asks exactly one targeted question and immediately returns to `TRIAGE`.            |
| `TOOL_EXECUTION`      | **Data retrieval.** An intermediate stage while a data operation runs (e.g. fetching open requests or favorites). Control returns to `TRIAGE`, `CONFIRMATION`, or `FINALIZE` once the tool completes. |
| `CONFIRMATION`        | **Pre-commit check.** The AI summarises the scoped request in 2–3 sentences and asks the user to confirm before proceeding to provider matching.               |
| `FINALIZE`            | **Provider matching and presentation.** The system automatically searches for matching providers on stage entry and presents them one by one. The user accepts one or declines all. |
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
- `CONFIRMATION → FINALIZE`: the system automatically performs a provider search in the same response stream; the result list is injected into the follow-up LLM call.
- `COMPLETED → PROVIDER_PITCH`: fires automatically (without an explicit LLM call) when the user is pitch-eligible (see §4). The LLM never needs to call this transition itself.
- `FINALIZE → TRIAGE`: triggered when the user explicitly cancels the entire provider search. If `FINALIZE` yields exactly 0 search results, the AI must explicitly inform the user, apologize, and transition immediately back to `TRIAGE` to prompt the user to broaden their criteria. Any previously created service request is cancelled before the transition.
- `FINALIZE → RECOVERY` (safety fallback): the system runs exactly three streaming passes (main stream + two follow-up streams) before triggering this fallback to explain the failure, then runs a fourth catch-up pass after the forced transition.
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

### 3.4 Clarification

- If the user's request lacks sufficient detail, the AI may enter `CLARIFY` to ask one targeted question before returning to `TRIAGE`.
- The AI must not over-probe. If the user has already provided sufficient detail across multiple short messages, the AI must skip probing and proceed to summarise and confirm.
- If the user signals that their description is complete (e.g. "do you know someone who can help me?"), the AI must immediately move to the summarise-and-confirm flow.

### 3.5 Interrupt Handling

- If the user speaks or sends a message while the AI is actively responding, the AI's current response must be cancelled before a new one is generated.
- Empty or noise-only audio that does not produce a valid text transcript must not trigger an interrupt of the AI's current response.
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

| Response   | System Action                                                              |
|------------|----------------------------------------------------------------------------|
| `accepted` | Mark user as service provider in authoritative DB; transition to `PROVIDER_ONBOARDING`. **Note:** Mirroring `is_service_provider = true` to the search index is deferred until the user successfully saves their first competency batch to prevent surfacing blank profiles in search. |
| `not_now`  | Reset the 30-day cooldown clock (user may be asked again later).           |
| `never`    | Store permanent opt-out; the user is never asked again.                    |

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

---

## 6. Service Request Flow

### 6.1 Happy Path

1. User describes a need → stage: `TRIAGE`.
2. AI optionally clarifies → stage: `CLARIFY → TRIAGE`.
3. AI confirms the request with the user → stages: `TRIAGE → CONFIRMATION`.
4. User explicitly confirms the summary.
5. System performs provider search and presents results → stages: `FINALIZE → COMPLETED`.

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
- The "problem summary" used as the basis for provider search is the most recent AI response text. If no AI response has been generated yet, the concatenation of raw user inputs accumulated during `TRIAGE` is used instead.

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
- When the AI transitions from `FINALIZE` back to `TRIAGE` (either due to zero results or user cancellation), any service request that was created during the current scoping flow must be cancelled automatically by the system before the transition completes. The AI does not need to prompt the user to confirm the cancellation; it is implicit in the transition.
- The `cancel_service_request` tool is available to the AI with write permission over service requests. It takes the current request identifier as a parameter. Calling it when no active request exists is a no-op.

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

- The client must not send messages before the data channel is fully open.
- Messages that arrive before the channel is ready must be buffered and sent immediately once the channel opens.

### 7.3 Mode Switching Within a Session

- Switching from voice to text mode within an active session does not require a new WebRTC connection. The client mutes the microphone and sends a `mode-switch: text` event, which causes the server to immediately interrupt any in-progress TTS output.
- Switching from text to voice mode acquires microphone permission and renegotiates the existing WebRTC connection to add an audio track. If microphone permission is denied, the switch fails silently and the session remains in text mode.
- If a voice track already exists but is muted (from a previous downgrade to text mode), switching back to voice unmutes the track and sends `mode-switch: voice` — no renegotiation is required.
- If a new audio track arrives on an existing voice session (e.g. Bluetooth device swap), the system replaces the input track and restarts the audio sub-tasks without resetting conversation state.
- If a text-to-voice upgrade is triggered but the audio track does not arrive within 5 seconds after the offer, the upgrade fails.

### 7.4 Client-Side Idle Timeout

- The client automatically terminates an active session after 10 consecutive minutes of inactivity (no incoming messages of any type). On timeout, the session is torn down, the full chat history is cleared, and the UI returns to its idle state.

### 7.5 Optimistic Message Display

- When a user submits a text message, the client adds it to the chat view immediately, before the server confirms receipt. If the server subsequently echoes the same message, the client must detect and discard the duplicate rather than displaying it twice.

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
- The settings update endpoint rejects any `language` value that is not `"en"` or `"de"` with HTTP 400. Settings are merged with existing values; unknown keys are ignored.

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

---

## 9. Connection Lifecycle

- Each WebRTC connection has a 10-minute server-side idle timer. If no user activity (voice transcript finalisation, text input, or mode switch) is detected within this window, the connection is automatically closed and all associated resources are released.
- The idle timer is reset on every user activity event. Empty audio chunks or audio classified purely as background noise by the VAD (Voice Activity Detection) must not reset the 10-minute idle timer.
- When a connection is closed (intentional or timeout), the current conversation stage is written as the final stage to the active AI conversation document (if one is open), and the runtime state machine is transitioned to its terminal state.
- An invalid `mode` query parameter (any value other than `"voice"` or `"text"`) on a WebSocket connection is silently coerced to `"text"` to prevent unintended audio playback in inappropriate environments.

### 9.1 Runtime FSM Bootstrap Sequence

- When a new session is established, the server-side agent runtime FSM is initialised in the `BOOTSTRAP` state.
- The FSM advances to `DATA_CHANNEL_WAIT` as soon as the WebRTC peer connection is negotiated and the data channel attachment is confirmed.
- Once the data channel is confirmed open, the FSM transitions to `LISTENING` (voice mode) or dispatches the text greeting and transitions to `LISTENING` (text mode).
- The current FSM state is emitted as a `runtime-state` message on both the initial data-channel attachment and again when the channel open event fires, ensuring the client always receives the correct state even if it connects after the FSM has already advanced past `BOOTSTRAP`.

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
- Text-mode sessions must never attempt to play audio or send a greeting.
- If the AI is speaking and new input arrives, the current speech output must be interrupted before processing the new input. The interrupted state must be handled gracefully with no orphaned history entries.
- The permanent opt-out sentinel for the provider pitch must be treated as a special value — never as a real date — throughout all date comparisons.
- Search input is capped at 20 unique words before being written to the search index to prevent embedding noise. While search input is capped at 20 unique words, it must also be capped at a maximum character length (e.g., 200 characters) to prevent a malicious user from submitting a single 10,000-character string without spaces to overload the embedding model.