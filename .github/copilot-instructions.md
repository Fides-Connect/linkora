# Fides - AI Voice Assistant Platform: Coding Agent Instructions

## Repository Overview

**Fides** is a complete voice-based AI assistant platform with real-time WebRTC audio streaming. The repository contains three main components:

1. **connectx/** - Flutter mobile application (iOS/Android) - Dart 3.9.2, Flutter 3.35.7+
2. **ai-assistant/** - Python WebRTC server with AI processing - Python 3.11+
3. **weaviate/** - Self-hosted vector database infrastructure - Docker/Podman

**Size**: Medium (~1600 statements in Python, ~50 Dart files)  
**Architecture**: Client-server with WebRTC peer-to-peer audio, WebSocket signaling, Firebase Authentication, and Weaviate vector database for semantic search.

## Critical Build Requirements

### Python Environment Setup (ai-assistant/)

**ALWAYS activate the virtual environment first**:
```bash
cd ai-assistant
source ../.venv/bin/activate  # Virtual environment is at repo root
```

**NEVER use `python` directly** - it's not in PATH. Use `python3` or activate venv.

### Flutter Environment Setup (connectx/)

**Flutter version**: 3.35.7 (Dart 3.9.2)

**Before ANY Flutter command**, ensure Firebase config exists:
```bash
cd connectx
./scripts/setup_firebase_for_ci.sh  # Creates stub firebase_options.dart if missing
```

**Then install dependencies**:
```bash
flutter pub get  # ALWAYS run before build/test/analyze
```

## Build & Test Commands

### AI-Assistant (Python)

**Test** (most common):
```bash
cd ai-assistant
source ../.venv/bin/activate
python -m pytest tests/ -v --cov=src/ai_assistant --cov-report=term-missing
```

**Test specific file**:
```bash
python -m pytest tests/test_user_management.py -v
```

**Run server locally** (requires .env configuration):
```bash
cd ai-assistant
source ../.venv/bin/activate
python main.py  # Starts on PORT from .env (default 8080)
```

**Docker build**:
```bash
cd ai-assistant
docker build -t ai-assistant -f Containerfile .
```

**Docker compose** (with Weaviate):
```bash
# Start Weaviate first
cd weaviate
docker-compose up -d

# Then start AI-Assistant
cd ../ai-assistant
docker-compose up -d
```

### ConnectX (Flutter)

**Analyze** (checks for errors without building):
```bash
cd connectx
./scripts/setup_firebase_for_ci.sh  # ALWAYS run first
flutter pub get
flutter analyze
```

**Test**:
```bash
cd connectx
./scripts/setup_firebase_for_ci.sh
flutter pub get
dart run build_runner build --delete-conflicting-outputs  # Generate mocks
flutter test
```

**Build Android APK**:
```bash
cd connectx
./scripts/setup_firebase_for_ci.sh
flutter pub get
flutter build apk --release
```

**Run for testing**:
```bash
cd connectx
flutter pub get
flutter run  # Requires connected device/emulator
```

**Run web** (uses port from .env):
```bash
cd connectx
./scripts/run_web.sh  # Reads WEB_PORT from .env (default 60099)
```

## Environment Configuration

### Required Before Running

**ai-assistant/.env** (copy from .env.template):
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to Google Cloud service account JSON
- `GEMINI_API_KEY` - Google Gemini API key (required)
- `GOOGLE_OAUTH_CLIENT_ID` - Web OAuth client ID for Firebase validation
- `USE_WEAVIATE` - Set to `false` for development (uses test data), `true` for production
- `WEAVIATE_URL` - Only if USE_WEAVIATE=true (default: http://localhost:8090)

**connectx/.env** (copy from template.env):
- `AI_ASSISTANT_SERVER_URL` - Server address (e.g., localhost:8080, or IP:8080)
- `GOOGLE_OAUTH_CLIENT_ID` - Web OAuth client ID from Firebase Console
- `WEB_PORT` - Port for web server (default: 60099)

**Note**: For Android emulator testing, use your computer's local network IP (e.g., 192.168.1.100:8080), NOT localhost.

## GitHub CI/CD Workflows

### .github/workflows/ai-assistant-test.yml

**Runs on**: Push/PR to main affecting `ai-assistant/**`

**Jobs**:
1. **unit-tests** - Runs pytest with coverage (Python 3.11)
2. **integration-test** - Full server test with health check and audio validation
   - Creates Google credentials from secrets
   - Starts server in background
   - Runs test_client.py with test audio
   - Validates output.wav file and audio content
   - **Timing**: Server startup max 30s, test timeout 2min

**Required secrets**: `GOOGLE_CREDENTIALS_JSON`, `GEMINI_API_KEY`

### .github/workflows/connectx-test.yml

**Runs on**: Push/PR to main affecting `connectx/**`

**Jobs**:
1. **build-and-test** - Uses devcontainers/ci to build/test in dev container
   - Runs setup_firebase_for_ci.sh
   - Runs flutter pub get
   - Runs build_runner to generate mocks
   - Runs flutter test
   - Builds APK

**Note**: Tests may have mock generation issues - see "Known Issues" section.

## Project Structure & Key Files

### Root Configuration
- `fides-dev-workspace.code-workspace` - VS Code workspace definition
- `.venv/` - Python virtual environment (shared by ai-assistant)
- `.devcontainer/` - Dev container config with Flutter SDK
- `README.md` - Main documentation
- `IMPLEMENTATION_NOTES.md` - User auth and FCM integration details
- `MULTI_USER_ARCHITECTURE.md` - Concurrent connection handling

### ai-assistant/
```
├── main.py                      # Entry point - runs ai_assistant.__main__
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Pytest configuration
├── Containerfile               # Docker image definition
├── docker-compose.yml          # Service orchestration
├── .env.template               # Environment template
├── scripts/
│   ├── run.sh                  # Container build/run helper
│   ├── init_weaviate.py        # Database initialization
│   └── cloud-deploy.sh         # Cloud deployment
├── src/ai_assistant/
│   ├── __main__.py             # Application startup (87 statements)
│   ├── signaling_server.py     # WebSocket server (177 statements)
│   ├── peer_connection_handler.py  # WebRTC connections (104 statements)
│   ├── ai_assistant.py         # Core AI logic (250 statements)
│   ├── audio_processor.py      # STT/TTS streaming (409 statements)
│   ├── common_endpoints.py     # HTTP endpoints (/health, /user/sync)
│   ├── weaviate_models.py      # DB models (User, Provider, ChatMessage)
│   ├── weaviate_config.py      # Schema definitions
│   ├── data_provider.py        # Data abstraction layer
│   ├── test_data.py            # Local test providers
│   └── prompts_templates.py    # LLM prompts
└── tests/
    ├── test_user_management.py
    ├── test_signaling_server.py
    ├── test_chat_history_persistence.py
    ├── test_langchain_history_integration.py
    └── test_client.py          # Integration test client
```

### connectx/
```
├── pubspec.yaml                # Flutter dependencies
├── analysis_options.yaml       # Dart linting rules
├── template.env                # Environment template
├── scripts/
│   ├── run_web.sh             # Web server runner
│   └── setup_firebase_for_ci.sh  # CI Firebase setup
├── lib/
│   ├── main.dart              # Entry point - initializes Firebase, Auth, WebRTC
│   ├── firebase_options.dart  # Generated by flutterfire configure
│   ├── firebase_options_stub.dart  # Stub for CI/testing
│   ├── theme.dart             # App theme
│   ├── services/
│   │   ├── auth_service.dart     # Firebase Authentication
│   │   ├── user_service.dart     # FCM tokens & user sync
│   │   ├── webrtc_service.dart   # WebRTC peer connections
│   │   ├── speech_service.dart   # Speech interaction logic
│   │   └── notification_service.dart
│   ├── pages/
│   │   └── start_page.dart       # Main UI
│   ├── widgets/               # UI components
│   └── localization/          # i18n support
├── android/                   # Android platform code
├── ios/                      # iOS platform code
└── test/
    ├── widget_test.dart
    └── services/             # Service unit tests
```

### weaviate/
```
├── docker-compose.yml         # Weaviate + text2vec-model2vec
└── README.md
```

## Architecture Details

### User Authentication Flow
- Firebase UID is used as primary identifier throughout system
- WebSocket connections include `?user_id={firebase_uid}` query parameter
- FCM tokens stored in Weaviate for push notifications
- Each user gets isolated AIAssistant instance with persistent chat history

### Multi-User Support
- `SignalingServer.user_assistants` - Dict mapping user_id → AIAssistant instance
- Conversation history persists across reconnections
- Multiple concurrent users fully supported with isolated state

### Conversation Stages
1. **GREETING** - Personalized greeting, asks user's needs
2. **TRIAGE** - Service coordinator mode, scoping questions
3. **FINALIZE** - Present matched providers (auto-transitions when AI says "database durchsuchen")
4. **COMPLETED** - Confirms and says goodbye

### Audio Pipeline
- Client captures at 48kHz mono → WebRTC stream to server
- Server: STT (accepts 48kHz natively) → LLM (Gemini 2.0) → TTS (48kHz output)
- Response streams back via WebRTC at 48kHz
- Uses gRPC streaming for 30-50% lower latency vs REST

## Known Issues & Workarounds

### Flutter Test Mocks
**Issue**: flutter analyze shows errors for missing mocks in tests  
**Cause**: build_runner hasn't generated mock files  
**Fix**: Run `dart run build_runner build --delete-conflicting-outputs` before testing  
**CI**: GitHub workflow includes this step

### Python 3.14 Compatibility
**Warning**: Pydantic V1 in langsmith not fully compatible with Python 3.14  
**Impact**: Warning message but tests pass  
**Workaround**: None needed, functionality works

### Android Emulator Connectivity
**Issue**: localhost doesn't work from Android emulator  
**Fix**: Use host machine's local network IP (e.g., 192.168.1.100:8080)  
**Configuration**: Set in connectx/.env as AI_ASSISTANT_SERVER_URL

### Virtual Environment Location
**Issue**: .venv is at repo root, not in ai-assistant/  
**Fix**: Always use `source ../.venv/bin/activate` from ai-assistant/  
**Why**: Shared across Python scripts at root level

## Validation Steps

### Pre-commit Checks
1. **Python tests**: `cd ai-assistant && source ../.venv/bin/activate && pytest tests/ -v`
2. **Flutter analyze**: `cd connectx && flutter pub get && flutter analyze`
3. **Flutter tests**: `cd connectx && dart run build_runner build && flutter test`

### Integration Test
```bash
# Terminal 1: Start server
cd ai-assistant && source ../.venv/bin/activate && python main.py

# Terminal 2: Run test client
cd ai-assistant && source ../.venv/bin/activate
python tests/test_client.py --audio-file tests/data/ai_assistant_test_input.wav
```

### Container Build Test
```bash
cd ai-assistant
docker build -t ai-assistant -f Containerfile .
# Should complete without errors
```

## Important Commands Reference

### Never use these:
- `python` (not in PATH - use `python3` or activate venv)
- `flutter` without `flutter pub get` first
- Build/test without environment file (.env or template.env)

### Always use these sequences:
**Python work**:
```bash
cd ai-assistant
source ../.venv/bin/activate
# Now run pytest/python commands
```

**Flutter work**:
```bash
cd connectx
./scripts/setup_firebase_for_ci.sh  # If firebase_options.dart missing
flutter pub get
# Now run flutter commands
```

## Trust These Instructions

These instructions have been validated by running commands and examining CI workflows. If you encounter an error:
1. Verify you followed the exact command sequence above
2. Check that .env files are configured
3. Ensure virtual environment is activated (Python)
4. Ensure flutter pub get was run (Flutter)

Only search for additional information if these instructions are incomplete or proven incorrect.
