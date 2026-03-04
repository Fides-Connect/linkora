# Linkora — Use Cases & Behaviours

> **Living document.** Every agent session that surfaces a new behavior, edge case, or invariant should append it to the relevant section below.
>
> **Agents: load only the section(s) relevant to your current task — do not load the entire file unless the task spans multiple domains.**

---

## Overall Goal

- Fides (branded "ConnectX") is an AI voice/chat assistant that matches users to service providers.
- The AI persona is named **Elin**.
- Two interaction modes exist: `voice` (WebRTC audio + DataChannel) and `text` (DataChannel only, no audio, `skip_greeting=True`).
- The system is designed to be language-agnostic; language flows top-down from the WebSocket query param — never hardcoded.

---

## Database

### Firestore (Source of Truth)

- Firestore holds the canonical state for users, service requests, competencies, reviews, and AI conversations.
- All REST endpoints write to Firestore first.
- `expires_at = now() + 30 days` is set on AI conversation docs for TTL cleanup.
- `PROVIDER_PITCH_OPT_OUT_SENTINEL = datetime(9999, 1, 1)` is stored in `last_time_asked_being_provider` to permanently opt a user out of the provider pitch. Defined in `firestore_schemas.py`.
- New users receive `last_time_asked_being_provider = now() - 60 days` via `auth/sync` so the first eligible conversation triggers the pitch.

### Weaviate (Read Cache — mirrors Firestore)

- Weaviate is not authoritative. It holds a denormalized read-optimized copy of provider competencies for vector/hybrid search.
- **Hub-spoke schema**: `User` (hub) ↔ `Competence` (spoke), linked bidirectionally.
- `sanitize_input()` caps input at 20 unique words before any Weaviate write to prevent embedding spam.
- Plain-text queries → vector search. JSON with `{available_time, location, criterions}` → hybrid search.
- Priority for connection: `WEAVIATE_URL` (local) takes precedence over `WEAVIATE_CLUSTER_URL` + `WEAVIATE_API_KEY` (cloud).
- In CI, Weaviate is auto-mocked via `conftest.py` patching `HubSpokeConnection.get_client`.

---

## Flutter App

### Navigation & State

- MVVM architecture: pages are stateless; all state lives in `ViewModel` (`ChangeNotifier`). Never call services from widgets.
- Platform APIs (`FirebaseAuth`, mic, WebRTC) are wrapped in `wrappers.dart` and always injected — never called directly.

### WebRTC / DataChannel

- **DataChannel guard**: `_dataChannelReady` must be `true` before any message is sent. Messages arriving before the channel is open are buffered in `_pendingTextMessage` and flushed on `onDataChannelOpen`. This guard must be preserved on all new send paths.
- Client → server message format: `{"type": "text-input", "text": "…"}`
- Server → client message format: `{"type": "chat", "text": "…", "isUser": bool, "isChunk": bool}`
- `isChunk=true` means the message is a streaming fragment; Flutter must assemble all fragments before displaying a complete message.

---

## Use Cases

### User → Service Provider Transition

- `is_service_provider` is set to `true` when the user's conversational message explicitly indicates intent to offer services (e.g. "I want to be a provider", "I can do this job").
- This transition is triggered via the `record_provider_interest` tool with outcome `"accepted"`, which sets `is_service_provider=True` in Firestore and returns `{"signal_transition": "provider_onboarding"}` to move the stage forward.
- Existing providers can also enter `PROVIDER_ONBOARDING` directly from `TRIAGE` (e.g. to update their skills).

### Provider Pitch Flow

- The AI pitches the provider opportunity only when all four conditions are true:
  1. `user.is_service_provider == False`
  2. `user.last_time_asked_being_provider` is not `None`
  3. `last_time_asked_being_provider` ≠ `PROVIDER_PITCH_OPT_OUT_SENTINEL`
  4. `now() - last_time_asked_being_provider >= 30 days`
- `record_provider_interest` outcomes:
  - `"accepted"` → `is_service_provider=True` + transition to `PROVIDER_ONBOARDING`
  - `"not_now"` → reset 30-day cooldown clock
  - `"never"` → write `PROVIDER_PITCH_OPT_OUT_SENTINEL` (permanent opt-out)

### Provider Onboarding Flow

- Multi-turn skill collection; the AI asks at most 2 questions per turn.
- Draft state is kept in `ConversationService.context["onboarding_draft"]` — in-memory only; lost if the session drops.
- Session ends with a Markdown summary of collected skills followed by a `save_competence_batch` tool call.

### Service Request Flow

- Users describe a need; the AI triages it, optionally clarifies, then calls `create_service_request` after user confirmation.
- Stage path: `TRIAGE → (CLARIFY →) TOOL_EXECUTION → CONFIRMATION → FINALIZE → COMPLETED`.
- `TRIAGE → FINALIZE` auto-triggers a Weaviate provider search in the same response stream.

### Session Reset & History

- LLM chat history is in-memory per `session_id` in `LLMService.session_store`. Not persisted to Firestore.
- Resetting a session means removing the entry from `session_store`; it does NOT clear the Firestore AI conversation document (which has its own 30-day TTL).

### Interrupt Handling

- `AudioProcessor.is_ai_speaking` must be checked on every new response-generation path.
- If a user speaks while the AI is speaking, the in-flight TTS pipeline is interrupted before a new response is generated.

---

## Conversation Stage FSM

> Full transition table is in `copilot-instructions.md`. Add edge-case notes here.

- Stage transitions happen **only** inside `ResponseOrchestrator.generate_response_stream()` via `handle_signal_transition_async()`. Never set `conversation_service.current_stage` directly — it desyncs prompt templates.
- `signal_transition` values returned by tools are handled in the stream loop, not dispatched through `AgentToolRegistry`.

---

## Known Gotchas & Edge Cases

- Text-mode sessions must always be constructed with `AudioProcessor(skip_greeting=True)`; omitting this causes an unwanted greeting playback attempt.
- `@pytest.mark.asyncio` is **not** used in this repo — `asyncio_mode = "auto"` is set globally in `pyproject.toml`.
- Never hardcode language strings (e.g. `'de'`); language must flow from the WS `?language=` param through every layer.
- The `AgentRuntimeFSM` is deterministic and must not be bypassed or replicated elsewhere. Its 11 states are: `BOOTSTRAP → DATA_CHANNEL_WAIT → LISTENING → THINKING → LLM_STREAMING → TOOL_EXECUTING → SPEAKING → INTERRUPTING → MODE_SWITCH → ERROR_RETRYABLE → TERMINATED`.
