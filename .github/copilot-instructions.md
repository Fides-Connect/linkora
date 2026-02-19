# Copilot Instructions — Linkora AI Voice/Chat Assistant Platform

## Project Identity
- **Platform**: Linkora — AI-powered voice and chat assistant for service provider matching
- **Company**: Allinked
- **AI Agent persona**: "Elin" — hardcoded in `ai-assistant/src/ai_assistant/ai_assistant.py`
- **Monorepo components**: `connectx/` (Flutter app), `ai-assistant/` (Python backend), `weaviate/` (vector DB)

## High-Level Architecture

The platform connects end-users (seeking services) with providers via an AI conversation that progressively gathers intent, searches Weaviate for matching providers, and creates a service request in Firestore.

```
ConnectX (Flutter) ──WS signaling──► SignalingServer
                   ◄──WebRTC audio + DataChannel────
                                        │
                               PeerConnectionHandler  (per-connection state, 10-min idle timer)
                                        │
                                  AudioProcessor      (STT→LLM→TTS hot path)
                                   ├── TranscriptProcessor  (gRPC streaming STT)
                                   ├── ResponseOrchestrator (stage FSM + LLM streaming)
                                   └── TtsPlaybackManager   (parallel sentence-level TTS)
```

**Two session modes** are set at connect-time as a WebSocket query param (`?mode=voice|text`):
- **voice**: mic audio is captured and sent; greeting is played on connection.
- **text**: no audio track sent; greeting is skipped; stage starts at `TRIAGE` immediately (`skip_greeting=True` in `AudioProcessor`). Text input arrives over the DataChannel as `{"type": "text-input", "text": "..."}`.

## Conversation Stage FSM — Critical Invariant

Stages: `GREETING → TRIAGE → FINALIZE → COMPLETED`

**All stage transitions happen exclusively inside `ResponseOrchestrator.generate_response_stream()`** via `ConversationService.detect_stage_transition()`. Never set `conversation_service.current_stage` directly from outside the orchestrator — doing so will desync the prompt templates from the actual stage.

The `TRIAGE → FINALIZE` transition auto-triggers: a Weaviate provider search + provider presentation generation within the same stream, without a new user message.

## DataChannel Protocol (Flutter ↔ Backend)

| Direction | Message shape | Meaning |
|---|---|---|
| Client → Server | `{"type": "text-input", "text": "…"}` | User typed a message (text mode) |
| Server → Client | `{"type": "chat", "text": "…", "isUser": bool, "isChunk": bool}` | Chat display update; `isChunk=true` = streaming fragment |

`isChunk=true` fragments must be assembled by the Flutter side before treating them as a complete message.

## Key Files

| File | Role |
|---|---|
| `ai-assistant/src/ai_assistant/signaling_server.py` | WS entry — reads `user_id`, `language`, `mode` query params |
| `ai-assistant/src/ai_assistant/peer_connection_handler.py` | Per-connection lifecycle; idle timer; DataChannel wiring |
| `ai-assistant/src/ai_assistant/audio_processor.py` | Owns the STT→LLM→TTS loop; interrupt detection via `is_ai_speaking` |
| `ai-assistant/src/ai_assistant/services/conversation_service.py` | `ConversationStage` constants + prompt templates per stage |
| `ai-assistant/src/ai_assistant/services/response_orchestrator.py` | Stage transitions + LLM streaming — **the only place stages advance** |
| `ai-assistant/src/ai_assistant/services/llm_service.py` | Gemini streaming via LangChain; per-session in-memory chat history |
| `ai-assistant/src/ai_assistant/data_provider.py` | `DataProvider` ABC; `get_data_provider()` always returns `WeaviateDataProvider` |
| `ai-assistant/src/ai_assistant/api/v1/router.py` | REST API surface (auth, /me, users, service-requests, chats, reviews) |
| `connectx/lib/services/webrtc_service.dart` | WebRTC + WS signaling client; mode-aware connect logic |
| `connectx/lib/services/speech_service.dart` | Facade over `WebRTCService`; exposes callbacks to the ViewModel |
| `connectx/lib/features/home/presentation/viewmodels/assistant_tab_view_model.dart` | All voice/chat UI state (`ConversationState`, message list, `_dataChannelReady` guard) |
| `connectx/lib/models/app_types.dart` | Shared enums (`ConversationState`) and callback typedefs (`OnChatMessageCallback`) |

## Developer Workflows

### Backend
```bash
cd ai-assistant && pip install -e ".[dev]"   # install into shared .venv at repo root
python -m ai_assistant                        # start server on :8080
python -m pytest tests/ -v --tb=short --cov=src/ai_assistant
docker-compose up                             # full stack incl. Weaviate
```
Only `GEMINI_API_KEY` is required. `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` is optional (falls back to ADC).

### Flutter
```bash
cd connectx
cp template.env .env   # set AI_ASSISTANT_SERVER_URL (use machine IP for Android emulator)
flutter pub get
flutter run
flutter test           # unit tests — no emulator needed
```
CI Flutter tests run inside a devcontainer (`.devcontainer/`) — don't use bare `flutter test` in CI.

## Project-Specific Conventions

### Python Backend
- **Fully async** throughout — no blocking I/O in the hot path. Use `asyncio` primitives.
- **Constructor injection** everywhere — services receive dependencies via `__init__`, not module-level singletons. Mock at the constructor boundary in tests.
- **No `@pytest.mark.asyncio`** needed — `asyncio_mode = "auto"` is set in `pyproject.toml`.
- **Weaviate auto-mocked in CI**: `conftest.py` detects Weaviate availability and patches `HubSpokeConnection.get_client` when offline. Tests pass in both environments.
- **Language flows top-down**: WS query param → `PeerConnectionHandler.language` → `AIAssistant` constructor → all services. Never assume German (`'de'`) is the only language.
- **LLM chat history** is in-memory per `session_id` inside `LLMService.session_store` — it is not persisted to Firestore. Clearing/resetting a session means removing from this dict.
- **Interrupt handling**: `AudioProcessor.is_ai_speaking` gates whether an incoming transcript triggers a new LLM response or cancels the current one. Do not skip this flag when adding new response-generation paths.
- **Text mode greeting skip**: `AudioProcessor(skip_greeting=True)` advances `ConversationService` to `TRIAGE` on `start()`. Without this, all text messages would be answered with the greeting prompt.

### Flutter
- **MVVM**: Pages are stateless/minimal. `ViewModel` (`ChangeNotifier`) owns all mutable state. Never reach past the ViewModel to call services from a widget.
- **Wrapper pattern**: Platform APIs (`FirebaseAuth`, microphone, WebRTC) are wrapped in `wrappers.dart`. Always inject wrappers — never call platform APIs directly — to keep services testable.
- **DataChannel readiness guard**: `_dataChannelReady` in `AssistantTabViewModel` must be `true` before sending text. A message sent too early is stored in `_pendingTextMessage` and flushed on `onDataChannelOpen`. This guard must be preserved when adding new DataChannel send paths.
- **Environment**: `flutter_dotenv` loads `.env` (copied from `template.env`). `AI_ASSISTANT_SERVER_URL` is the only required variable.
- **`OnChatMessageCallback` signature**: `(String text, bool isUser, bool isChunk)` — `isChunk=true` is a streaming fragment, not a complete message. UI must handle partial assembly.

### Weaviate / Provider Data
- Schema is **hub-spoke**: `Competence` is the hub; `User` (provider) objects are the spokes, linked bidirectionally.
- `data_provider.py`: `search_providers()` auto-detects the query type — plain text → vector search; JSON string `{"available_time", "location", "criterions"}` → `HubSpokeSearch.hybrid_search_providers()`.
- `hub_spoke_ingestion.py`: `sanitize_input()` enforces SEO spam defense (caps at 20 unique words) before any write to Weaviate.
- Connection: `WEAVIATE_URL` (local) takes priority over `WEAVIATE_CLUSTER_URL` + `WEAVIATE_API_KEY` (cloud), resolved in `WeaviateConnection.get_client()`.

### REST API (Backend)
All endpoints are under `/api/v1/` and require a Firebase Bearer token except health checks. Key groupings:
- **Auth**: `/auth/sign-in-google`, `/auth/sync`, `/auth/logout`
- **Profile**: `/me` (get/patch), `/me/competencies` (CRUD), `/me/favorites` (CRUD)
- **Service flow**: `/service-requests` → `/service-requests/{id}/chats` → `/service-requests/{id}/chats/{chat_id}/messages`
- **Reviews**: `/reviews` (CRUD)

## External Dependencies

| Service | Used for | Key env var |
|---|---|---|
| Google Gemini (`gemini-2.5-flash`) | LLM responses | `GEMINI_API_KEY` |
| Google Cloud Speech-to-Text (gRPC) | Audio → text, 30–50% lower latency than REST | GCP credentials |
| Google Cloud TTS (Chirp3-HD) | Text → audio; voice: `de-DE-Chirp3-HD-Sulafat` / `en-US-Chirp3-HD-Sulafat` | GCP credentials |
| Firebase Auth | JWT verification on all REST endpoints | `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` |
| Firestore | Users, service requests, chats, reviews | same credentials |
| Weaviate | Provider vector/hybrid search | `WEAVIATE_URL` or `WEAVIATE_CLUSTER_URL` + `WEAVIATE_API_KEY` |
