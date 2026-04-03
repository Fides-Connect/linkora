# Copilot Instructions — Linkora

## Project Overview
- **Platform**: Linkora — AI voice/chat assistant matching users to service providers
- **Stack**: `connectx/` (Flutter), `ai-assistant/` (Python/aiohttp), `weaviate/` (vector DB)
- **AI persona**: "Elin" — `AGENT_NAME = "Elin"` in `ai_assistant.py`

## Living Specifications / Requirements Reference


`linkora_specifications.md` at the **repo root** is the authoritative Lastenheft — the complete set of observable system behaviours, use cases, edge cases, and invariants that every agent must respect and must never violate.

### How agents must use this file
1. **Mandatory first step — read the entire file before acting**: at the start of every session, use a file-read tool to load the full contents of `linkora_specifications.md`. Do not proceed with any work until this is done.
2. **Treat it as inviolable constraints**: every behaviour described in `linkora_specifications.md` is a hard requirement. No code change, refactor, or new feature may silently remove, bypass, or contradict a behaviour defined there. If a task appears to conflict with an existing behaviour, flag it to the user before proceeding.
3. **During work**: if the code and `linkora_specifications.md` disagree, flag it — do not silently pick one.
4. **Mandatory last step — Lastenheft extraction after every task**: before ending the session, re-read the full conversation and apply the following filter to every decision, fix, behaviour, or constraint that surfaced:
   - **Ask**: *"Is this a statement about what the system shall do or how it shall behave in a specific scenario?"*
   - **If yes** → add it to `linkora_specifications.md` in the appropriate numbered section. Write it as a clear behavioural requirement: what triggers it and what the system must do. Do **not** include class names, file paths, method names, or implementation details.
   - **If no** (e.g. it is a code refactor detail, a test helper, a CI trick, a script invocation) → do not add it.
   - If an existing entry is now incorrect or superseded, update it in place.
   - If no new Lastenheft-relevant content was found, make no change to the file.

### Maintenance rules
- `linkora_specifications.md` is a **Lastenheft** — it describes observable system behaviours and scenarios only. Implementation details (class names, file paths, internal tooling, test setup) must not appear in this file.
- One numbered section per domain. Do not create new top-level sections without user confirmation.
- Each entry must be a concise behavioural statement: what triggers it and what the system must do.
- The file is enriched incrementally — every agent session that surfaces a new behavioural insight should leave the file better than it found it.

## Architecture

```
ConnectX (Flutter) ──WS signaling──► SignalingServer
                   ◄──WebRTC audio + DataChannel────
                                        │
                               PeerConnectionHandler  (per-connection state, 10-min idle timer)
                                        │
                                  AudioProcessor      (STT→LLM→TTS hot path)
                                   ├── TranscriptProcessor   (gRPC streaming STT)
                                   ├── ResponseOrchestrator  (ConversationStage FSM + LLM streaming)
                                   │    ├── AgentRuntimeFSM  (deterministic 11-state runtime FSM)
                                   │    └── AgentToolRegistry (tool dispatch + capability checks)
                                   └── TtsPlaybackManager    (parallel sentence-level TTS)
```

**Session modes** (WS query param `?mode=voice|text`):
- `voice`: mic audio sent; greeting played on connect.
- `text`: no audio; `skip_greeting=True`; starts at `TRIAGE`. Input via DataChannel `{"type": "text-input", "text": "..."}`.

## Critical Invariants

### Conversation Stage FSM
**Stage transitions happen ONLY inside `ResponseOrchestrator.generate_response_stream()`** via `handle_signal_transition_async()`. Never set `conversation_service.current_stage` directly — it will desync prompt templates.

| From | To (allowed) |
|---|---|
| `TRIAGE` | `CONFIRMATION`, `CLARIFY`, `TOOL_EXECUTION`, `RECOVERY`, `PROVIDER_ONBOARDING` |
| `CLARIFY` | `TRIAGE` |
| `TOOL_EXECUTION` | `TRIAGE`, `CONFIRMATION`, `FINALIZE` |
| `CONFIRMATION` | `FINALIZE`, `TRIAGE` |
| `FINALIZE` | `COMPLETED`, `RECOVERY` |
| `RECOVERY` | `TRIAGE` |
| `COMPLETED` | `PROVIDER_PITCH` |
| `PROVIDER_PITCH` | `PROVIDER_ONBOARDING`, `COMPLETED` |
| `PROVIDER_ONBOARDING` | `COMPLETED` |

Auto-triggers: `CONFIRMATION → FINALIZE` runs Weaviate search in the same stream; `COMPLETED → PROVIDER_PITCH` fires when user is eligible. Direct `TRIAGE → FINALIZE` is **illegal** — the mandatory confirmation gate requires passing through `CONFIRMATION` first.

### Provider Pitch Eligibility
All conditions must be true:
1. `user.is_service_provider == False`
2. `user.last_time_asked_being_provider` is not `None`
3. Value ≠ `PROVIDER_PITCH_OPT_OUT_SENTINEL` (`datetime(9999,1,1)`, permanent opt-out — defined in `firestore_schemas.py`)
4. `now() - last_time_asked_being_provider >= 30 days`

New users get `last_time_asked_being_provider = now() - 60 days` via `auth/sync`, so the first eligible conversation triggers the pitch.

**`record_provider_interest` outcomes**: `"accepted"` → `is_service_provider=True` + `{"signal_transition": "provider_onboarding"}`; `"not_now"` → reset 30-day clock; `"never"` → set sentinel.

**`PROVIDER_ONBOARDING`**: multi-turn skill collection (max 2 questions/turn). Draft in `ConversationService.context["onboarding_draft"]` (in-memory only — lost on session drop). Ends with Markdown summary + `save_competence_batch`. Existing providers can also enter from `TRIAGE`.

## AgentRuntimeFSM
Deterministic 11-state machine (no LLM). States: `BOOTSTRAP → DATA_CHANNEL_WAIT → LISTENING → THINKING → LLM_STREAMING → TOOL_EXECUTING → SPEAKING → INTERRUPTING → MODE_SWITCH → ERROR_RETRYABLE → TERMINATED`. Do not bypass or replicate this FSM.

## Tool Registry & Capabilities
`AgentToolRegistry.execute()` enforces `ToolCapability` before dispatch. Raises `ToolPermissionError` on missing cap. `signal_transition` is handled directly in the stream loop — never dispatched through the registry. A tool may also trigger a stage change by returning `{"signal_transition": "stage_name"}` in its result.

| Tool | Capability |
|---|---|
| `search_providers` | `("providers", "read")` |
| `get_favorites` | `("favorites", "read")` |
| `get_open_requests` | `("service_requests", "read")` |
| `create_service_request` | `("service_requests", "write")` |
| `record_provider_interest` | `("provider_onboarding", "write")` |
| `get_my_competencies` | `("provider_onboarding", "write")` |
| `save_competence_batch` | `("provider_onboarding", "write")` |
| `delete_competences` | `("provider_onboarding", "write")` |

## DataChannel Protocol

| Direction | Message |
|---|---|
| Client → Server | `{"type": "text-input", "text": "…"}` |
| Server → Client | `{"type": "chat", "text": "…", "isUser": bool, "isChunk": bool}` |

`isChunk=true` = streaming fragment; Flutter must assemble before display.

## Key Files

| File | Role |
|---|---|
| `ai-assistant/src/ai_assistant/signaling_server.py` | WS entry — reads `user_id`, `language`, `mode` |
| `ai-assistant/src/ai_assistant/peer_connection_handler.py` | Per-connection lifecycle; idle timer; DataChannel wiring |
| `ai-assistant/src/ai_assistant/audio_processor.py` | STT→LLM→TTS loop; interrupt gate via `is_ai_speaking` |
| `ai-assistant/src/ai_assistant/ai_assistant.py` | Facade — wires all services; builds 8-tool registry |
| `ai-assistant/src/ai_assistant/services/conversation_service.py` | `ConversationStage` enum, `_LEGAL_TRANSITIONS`, prompt dispatch |
| `ai-assistant/src/ai_assistant/services/response_orchestrator.py` | **Only place stages advance** — FSM, tools, provider pitch |
| `ai-assistant/src/ai_assistant/services/agent_runtime_fsm.py` | Deterministic `AgentRuntimeFSM` |
| `ai-assistant/src/ai_assistant/services/agent_tools.py` | `AgentTool`, `AgentToolRegistry`, `ToolCapability` |
| `ai-assistant/src/ai_assistant/services/llm_service.py` | Gemini streaming; in-memory chat history; tool-call assembly |
| `ai-assistant/src/ai_assistant/services/ai_conversation_service.py` | AI conversation persistence; 30-day TTL |
| `ai-assistant/src/ai_assistant/prompts_templates.py` | All LLM prompt strings |
| `ai-assistant/src/ai_assistant/firestore_schemas.py` | Pydantic schemas; `PROVIDER_PITCH_OPT_OUT_SENTINEL` |
| `ai-assistant/src/ai_assistant/hub_spoke_ingestion.py` | Weaviate write/ingest; `sanitize_input()` |
| `ai-assistant/src/ai_assistant/api/v1/endpoints/auth.py` | `sign_in_google`, `user_sync`, `user_logout` |
| `ai-assistant/src/ai_assistant/api/v1/endpoints/me.py` | `/me` get/patch; `/me/competencies` CRUD |
| `connectx/lib/services/webrtc_service.dart` | WebRTC + WS signaling client |
| `connectx/lib/services/speech_service.dart` | Facade over `WebRTCService`; exposes callbacks |
| `connectx/lib/features/home/presentation/viewmodels/assistant_tab_view_model.dart` | Voice/chat UI state; `_dataChannelReady` guard |
| `connectx/lib/models/app_types.dart` | `ConversationState` enum; `OnChatMessageCallback` typedef |

## Developer Workflows

### Backend
```bash
cd ai-assistant && pip install -e ".[dev]"
python -m ai_assistant          # starts on :8080
python -m pytest tests/ -v --tb=short --cov=src/ai_assistant
docker-compose up               # full stack incl. Weaviate
```
Only `GEMINI_API_KEY` is required.

### Flutter
```bash
cd connectx && cp .env.template .env   # set AI_ASSISTANT_SERVER_URL (machine IP for Android emulator)
flutter pub get && flutter run
flutter test                          # no emulator needed
```
CI runs inside `.devcontainer/` — do not use bare `flutter test` in CI.

## Coding Conventions

### Python Backend
- **Fully async** — no blocking I/O in the hot path. Use `asyncio` primitives.
- **Constructor injection** — no module-level singletons. Mock at constructor boundary in tests.
- **No `@pytest.mark.asyncio`** — `asyncio_mode = "auto"` in `pyproject.toml`.
- **Weaviate auto-mocked in CI** — `conftest.py` patches `HubSpokeConnection.get_client` when offline.
- **Language top-down**: WS param → `PeerConnectionHandler` → `AIAssistant` → all services. Never hardcode `'de'`.
- **LLM history**: in-memory per `session_id` in `LLMService.session_store`. Not persisted. Reset = remove from dict.
- **Interrupt gate**: `AudioProcessor.is_ai_speaking` must be checked on every new response-generation path.
- **Text mode**: always construct `AudioProcessor(skip_greeting=True)` for text sessions.
- **AI conversation TTL**: `expires_at = now() + 30 days` on Firestore docs; session reset only clears `LLMService.session_store`.
- **TDD**: write tests first.

### Flutter
- **MVVM**: Pages stateless. `ViewModel` (`ChangeNotifier`) owns all state. Never call services from widgets.
- **Wrapper pattern**: Platform APIs (`FirebaseAuth`, mic, WebRTC) wrapped in `wrappers.dart` — always inject, never call directly.
- **DataChannel guard**: `_dataChannelReady` must be `true` before sending. Early messages go to `_pendingTextMessage`, flushed on `onDataChannelOpen`. Preserve this guard on all new send paths.
- **`OnChatMessageCallback`**: `(String text, bool isUser, bool isChunk)` — `isChunk=true` is a fragment, not a complete message.

### Weaviate
- **Hub-spoke schema**: `User` (hub) ↔ `Competence` (spoke), linked bidirectionally.
- `search_providers()`: plain text → vector search; JSON with `{available_time, location, criterions}` → hybrid search.
- `sanitize_input()` caps at 20 unique words before any Weaviate write.
- Priority: `WEAVIATE_URL` (local) > `WEAVIATE_CLUSTER_URL` + `WEAVIATE_API_KEY` (cloud).

### REST API
All under `/api/v1/`, Firebase Bearer token required. Routes: `/auth/*`, `/me`, `/me/competencies`, `/me/favorites`, `/service-requests`, `/reviews`, `/ai-conversations`.

## External Dependencies

| Service | Purpose | Env var |
|---|---|---|
| Google Gemini (`gemini-2.5-flash`) | LLM responses | `GEMINI_API_KEY` |
| Google Cloud Speech-to-Text (gRPC) | Audio → text, 30–50% lower latency than REST | GCP credentials |
| Google Cloud TTS (Chirp3-HD) | Text → audio; voice: `de-DE-Chirp3-HD-Sulafat` / `en-US-Chirp3-HD-Sulafat` | GCP credentials |
| Firebase Auth | JWT verification on all REST endpoints | GKE Workload Identity / ADC |
| Firestore | Users, service requests, chats, reviews | same credentials |
| Weaviate | Provider vector/hybrid search | `WEAVIATE_URL` or `WEAVIATE_CLUSTER_URL` + `WEAVIATE_API_KEY` |
