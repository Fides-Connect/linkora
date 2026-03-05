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
  - **Text mode**: the user types; the AI responds with text only. No greeting is played on connection.
- All AI responses and prompts are language-aware. The language is set per session by the client and must be respected throughout the entire conversation. It must never be hardcoded.

---

## 2. Data Integrity Rules

### 2.1 Source of Truth

- Firestore is the authoritative data store. All persistent state (users, service requests, competencies, reviews, AI conversations) is written there first.
- The search index (Weaviate) is a read-optimised cache. It mirrors provider competencies for vector and hybrid search. It is never the source of truth.

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

- Automatically generated conversation topic titles must not exceed 300 characters before being stored. Titles exceeding this limit must be truncated silently.

---

## 3. Conversation Flow

### 3.1 Session Start

- **Voice mode**: the AI greets the user by his name immediately upon connection.
- **Text mode**: The AI greets the user by his name immediately when the page Assistant is opened. The conversation starts at the triage stage.

### 3.2 Conversation Stages

The conversation progresses through a finite set of named stages. Each stage represents a distinct phase of the dialogue with its own prompt behaviour and transition rules.

| Stage                 | Purpose                                                                                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `GREETING`            | **Welcome.** The AI greets the user by name and checks whether they have an open service request, then invites them to share their need.                      |
| `TRIAGE`              | **Scoping.** The AI acts as a service coordinator: it asks focused questions to understand the user's need just well enough to find a matching provider. It also detects provider-management intent and routes accordingly. |
| `CLARIFY`             | **Disambiguation.** Used when the request is too ambiguous to scope. The AI asks exactly one targeted question and immediately returns to `TRIAGE`.            |
| `TOOL_EXECUTION`      | **Data retrieval.** An intermediate stage while a data operation runs (e.g. fetching open requests or favorites). Control returns to `TRIAGE` or `CONFIRMATION` once the tool completes. |
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
| `TRIAGE`              | `FINALIZE`, `CLARIFY`, `TOOL_EXECUTION`, `RECOVERY`, `PROVIDER_ONBOARDING`                 |
| `CLARIFY`             | `TRIAGE`                                                                                    |
| `TOOL_EXECUTION`      | `TRIAGE`, `CONFIRMATION`, `FINALIZE`                                                        |
| `CONFIRMATION`        | `FINALIZE`, `TRIAGE`                                                                        |
| `FINALIZE`            | `COMPLETED`, `RECOVERY`, `TRIAGE`                                                           |
| `RECOVERY`            | `TRIAGE`                                                                                    |
| `COMPLETED`           | `PROVIDER_PITCH`, `TRIAGE`                                                                  |
| `PROVIDER_PITCH`      | `PROVIDER_ONBOARDING`, `COMPLETED`, `TRIAGE`                                                |
| `PROVIDER_ONBOARDING` | `COMPLETED`, `TRIAGE`                                                                       |

**Transition notes:**

- `TRIAGE → FINALIZE`: the system automatically performs a provider search in the same response stream; the result list is injected into the follow-up LLM call.
- `COMPLETED → PROVIDER_PITCH`: fires automatically (without an explicit LLM call) when the user is pitch-eligible (see §4). The LLM never needs to call this transition itself.
- `FINALIZE → TRIAGE`: triggered when the user explicitly cancels the entire provider search (e.g. "they are all too expensive", "never mind"). Any previously created service request is cancelled before the transition.
- `FINALIZE → COMPLETED` (safety fallback): if all follow-up response streams are exhausted and the stage is still `FINALIZE`, the system force-advances to `COMPLETED` to prevent the conversation from getting permanently stuck.
- `COMPLETED → TRIAGE`: triggered when the user indicates they have another need after the current flow concludes. The request context is cleared before entering `TRIAGE`.
- `PROVIDER_PITCH → TRIAGE`: triggered when the user, during the pitch, says they actually want to find a service provider rather than become one.
- `PROVIDER_ONBOARDING → TRIAGE`: triggered when the user declines the provider role (STEP 0 "no") or switches intent to finding a service instead of managing their own skills.
- Any back-transition to `TRIAGE` from `COMPLETED`, `FINALIZE`, `PROVIDER_PITCH`, or `PROVIDER_ONBOARDING` clears the per-request context so the new scoping session starts clean.

### 3.3 Clarification

- If the user's request lacks sufficient detail, the AI may enter `CLARIFY` to ask one targeted question before returning to `TRIAGE`.
- The AI must not over-probe. If the user has already provided sufficient detail across multiple short messages, the AI must skip probing and proceed to summarise and confirm.
- If the user signals that their description is complete (e.g. "do you know someone who can help me?"), the AI must immediately move to the summarise-and-confirm flow.

### 3.4 Interrupt Handling

- If the user speaks or sends a message while the AI is actively responding, the AI's current response must be cancelled before a new one is generated.
- When a response is interrupted, any partial user input that triggered the interrupt must be preserved and prepended to the user's next message, so the full accumulated request is processed coherently in the following turn.
- The system must not produce a situation where the conversation history contains consecutive user messages with no AI reply between them, as this causes the AI to lose conversational context.

### 3.5 Rapid Message Bursts

- When a user sends multiple messages in rapid succession (voice or text), each new message cancels the previous in-flight response.
- The system must coalesce all interrupted fragments so that the final response addresses the full intent of all the burst messages, not just the last one.

---

## 4. Provider Pitch Flow

### 4.1 Eligibility

The AI shall pitch the provider opportunity to a user only when **all four** of the following conditions are true:

1. The user is not already a service provider.
2. The user's provider-pitch opt-in timestamp has been set (i.e. not null).
3. The user has not permanently opted out (the timestamp must not equal the permanent opt-out sentinel).
4. At least 30 days have elapsed since the user was last asked.

New users have their timestamp pre-set to 60 days in the past, so the first eligible completed conversation triggers the pitch.

### 4.2 Auto-Trigger

- The pitch is triggered automatically when a conversation reaches `COMPLETED` and the user is eligible.
- The conversation advances to `PROVIDER_PITCH`; no explicit user action is required.

### 4.3 User Responses to the Pitch

| Response   | System Action                                                              |
|------------|----------------------------------------------------------------------------|
| `accepted` | Mark user as service provider; transition to `PROVIDER_ONBOARDING`.        |
| `not_now`  | Reset the 30-day cooldown clock (user may be asked again later).           |
| `never`    | Store permanent opt-out; the user is never asked again.                    |

---

## 5. Provider Onboarding Flow

- Onboarding is a multi-turn skill collection conversation.
- The AI asks at most 2 questions per turn to avoid overwhelming the user.
- All collected skill data is held in the session draft until the user confirms.
- The session ends with the AI presenting a Markdown summary of collected skills, followed by saving the full batch.
- Onboarding draft state is session-scoped. If the session drops, the draft is lost and onboarding must restart.
- Existing providers may also enter onboarding to update their skills (triggered from the triage stage).

---

## 6. Service Request Flow

### 6.1 Happy Path

1. User describes a need → stage: `TRIAGE`.
2. AI optionally clarifies → stage: `CLARIFY → TRIAGE`.
3. AI confirms the request with the user → stages: `TOOL_EXECUTION → CONFIRMATION`.
4. User confirms → stage: `FINALIZE`.
5. System performs provider search and presents results → stage: `COMPLETED`.

### 6.2 Provider Search

- A plain-text description triggers a semantic (vector) search.
- A structured query with `available_time`, `location`, and `criterions` triggers a hybrid search.
- If provider search results are already cached for the current `FINALIZE` stage, the system must return the cached results and not repeat the search.
- Exception: if the first search returned zero results (e.g. due to stale index data), the next search attempt must perform a real search rather than returning the cached empty list.

### 6.3 Tool Execution

- Tools that require specific permissions must not execute without those permissions. A permission failure must be surfaced as a handled error, not a silent skip.
- A tool may signal a stage transition by including a `signal_transition` value in its result. This transition is handled by the conversation stream.

---

## 7. Client–Server Communication Protocol

### 7.1 Message Format

| Direction       | Message Structure                                                  |
|-----------------|--------------------------------------------------------------------|
| Client → Server | `{"type": "text-input", "text": "…"}`                              |
| Server → Client | `{"type": "chat", "text": "…", "isUser": bool, "isChunk": bool}`   |

- `isChunk: true` means the message is a streaming fragment. The client must accumulate all fragments before treating the message as complete and displaying it.

### 7.2 Connection Readiness Guard

- The client must not send messages before the data channel is fully open.
- Messages that arrive before the channel is ready must be buffered and sent immediately once the channel opens.

---

## 8. REST API Behaviour

- All REST endpoints require a valid authentication token (Firebase Bearer).
- Write operations go to Firestore first; the search index is updated subsequently.
- The login sync endpoint must be idempotent — repeated calls with the same user data must not degrade or corrupt existing data.

---

## 9. Edge Cases & Invariants

- The system must never hardcode a language string. Language must flow from the session parameter through every layer of processing.
- Text-mode sessions must never attempt to play audio or send a greeting.
- If the AI is speaking and new input arrives, the current speech output must be interrupted before processing the new input. The interrupted state must be handled gracefully with no orphaned history entries.
- The permanent opt-out sentinel for the provider pitch must be treated as a special value — never as a real date — throughout all date comparisons.
- Search input is capped at 20 unique words before being written to the search index to prevent embedding noise.
