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
- **Provider search gate**: `hybrid_search_providers` filters competencies by `owned_by.is_service_provider == True`. If a user's Weaviate hub node is missing or has this flag as `False`, they return zero results regardless of how many competencies exist in Firestore. When 0 results are returned, an INFO-level log emits the count of competencies with `is_service_provider=True` to diagnose whether the issue is a missing flag or a vocabulary mismatch.
- **Hub node self-heal on login**: `POST /api/v1/auth/sync` calls `update_user_hub_properties` on every login. If the call returns `False` (hub node absent), it immediately creates the hub node from Firestore data and re-syncs all competencies — preventing the user from being invisible in searches after a Weaviate re-init. Owned by `api/v1/endpoints/auth.py`.
- **FINALIZE search cache-skip guard**: `ResponseOrchestrator` caches the provider list when FINALIZE is entered (auto-search) and returns the cache if the LLM tries to call `search_providers` again within the same stage. The cache is only used when non-empty — if `providers_found == []` (first search was interrupted or returned 0 due to stale data), the next `search_providers` tool call performs a real Weaviate round-trip. Owned by `services/response_orchestrator.py`.
- **Manual repair**: run `python scripts/repair_weaviate_user.py <user_id>` against any user who is not appearing in provider search results. This script reads Firestore as ground truth, creates or updates the hub node, and fully re-syncs competencies with correct `availability_tags`.

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
- **History repair on interrupt** (added 2026-03-04): Langchain's `RunnableWithMessageHistory.astream()` commits a `HumanMessage` to history at stream-start, before a single AI token is produced. When the task is cancelled mid-stream (rapid STT bursts, rapid chat messages), the `HumanMessage` is orphaned in history with no following `AIMessage`. This produces consecutive `HumanMessage` runs that cause Gemini to lose context and re-ask the user's top-level intent. Fix: `_trigger_interrupt()` calls `LLMService.pop_trailing_human_message()` to remove the orphaned message and appends it to `AudioProcessor._interrupted_text_buffer`. The next `process_text_input()` call prepends all stashed fragments to the new input, so the LLM receives the full accumulated request in one coherent turn. Owned by `audio_processor.py` + `llm_service.py`.

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
- **Rapid multi-message bursts** (voice STT or text mode): when a user sends multiple messages in quick succession, each new message cancels the previous LLM task. Without history repair the LLM sees consecutive `HumanMessage`s with no AI replies, causing it to forget earlier context and re-ask top-level intent. See history repair in Interrupt Handling above.
- **TRIAGE over-probing prevention**: the `TRIAGE_CONVERSATION_PROMPT` includes a "Fast-path" step (step 2): if the user has already provided sufficient detail across multiple short messages, the LLM must skip probing and jump directly to summarising. Phrases like "do you know someone who can help me?" signal the user considers their brief complete and should trigger an immediate summarise+confirm flow. Owned by `prompts_templates.py`.
