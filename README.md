<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="connectx/assets/images/LinkoraLogo.png">
    <img src="connectx/assets/images/LinkoraLogoDark.png" alt="Linkora" width="280">
  </picture>
</p>

<p align="center">
  <strong>AI-powered service marketplace assistant — voice &amp; chat, end-to-end open source.</strong>
</p>

<p align="center">
  <a href="docs/getting-started.md">Getting Started</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/connectx.md">Mobile App</a> ·
  <a href="docs/ai-assistant.md">Backend</a> ·
  <a href="docs/deployment.md">Deployment</a>
</p>

---

Linkora is a production-ready platform that lets users find local service providers through a **natural conversation** — by voice or text. The AI assistant (named **Elin**) guides the user, collects requirements, and returns ranked, enriched provider results. Developers get a complete, deployable stack: a Flutter mobile app, a Python WebRTC server, and a vector database, all wired together and ready to customise.

## 📱 App Screenshots

<table>
  <tr>
    <td align="center" width="25%">
      <img src="docs/assets/Linkora-Full-Assistant.png" alt="Assistant – Full Mode" width="180"><br>
      <sub><b>Assistant · Full Mode</b></sub><br>
      <sub>Voice &amp; text conversation powered by Weaviate provider search</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/assets/Linkora-Full-Settings.png" alt="Settings – Full Mode" width="180"><br>
      <sub><b>Settings · Full Mode</b></sub><br>
      <sub>Language, appearance &amp; notification preferences</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/assets/Linkora-Lite-Assistant.png" alt="Assistant – Lite Mode" width="180"><br>
      <sub><b>Assistant · Lite Mode</b></sub><br>
      <sub>Text-only chat backed by the Google Places API</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/assets/Linkora-Lite-Assistant-Results.png" alt="Search Results – Lite Mode" width="180"><br>
      <sub><b>Results · Lite Mode</b></sub><br>
      <sub>AI-curated provider cards with contact &amp; request actions</sub>
    </td>
  </tr>
</table>

## ✨ What Makes Linkora Different

| | |
|---|---|
| 🎙️ **Voice-first UX** | Real-time WebRTC audio streaming with Google STT/TTS — sub-second round-trips |
| 🤖 **Conversational search** | Elin asks the right questions, extracts structured intent, then fires a semantic search |
| 🔀 **Two deployment modes** | **Full** (Weaviate vector DB, onboarded providers) or **Lite** (Google Places + web enrichment, zero infra) |
| 🔒 **Secure by design** | All API keys stay server-side; clients authenticate via Firebase |
| 📦 **Batteries included** | Docker Compose, Cloud Run deploy scripts, GitHub Actions CI/CD, dev container |
| 🧪 **Well tested** | 60+ backend unit tests, Flutter widget tests, coverage reporting |

## 🏗️ Platform Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Linkora Platform                        │
├────────────────┬──────────────────────┬─────────────────────┤
│  ConnectX      │   AI-Assistant       │  Weaviate           │
│  Flutter app   │   Python / FastAPI   │  Vector DB          │
│  iOS & Android │   WebRTC server      │  (Full mode only)   │
│  Firebase Auth │   Gemini 3.0 LLM     │  Semantic search    │
│                │   STT / TTS          │  Provider profiles  │
└────────────────┴──────────┬───────────┴─────────────────────┘
                            │ WebRTC audio stream
                            ▼
                     User's mobile device
```

**Read more**: [Architecture Overview](docs/architecture.md)


## 📁 Repository Structure

```
linkora/
├── docs/                 # 📖 Comprehensive documentation
│   ├── README.md        # Documentation index
│   ├── getting-started.md
│   ├── architecture.md
│   ├── connectx.md
│   ├── ai-assistant.md
│   ├── weaviate.md
│   └── deployment.md
│
├── connectx/             # 📱 Flutter mobile application
│   ├── lib/             # Dart source code
│   ├── android/         # Android platform
│   ├── ios/             # iOS platform
│   └── test/            # Tests
│
├── ai-assistant/         # 🤖 Python WebRTC server
│   ├── src/             # Python source code
│   ├── scripts/         # Utility scripts (incl. download_models.py)
│   ├── tests/           # Unit and integration tests
│   ├── models/          # Bundled ML models (Git LFS — run `git lfs pull`)
│   ├── Dockerfile       # Container definition
│   └── docker-compose.yml
│
├── weaviate/             # 🗄️ Weaviate docker-compose + VM startup script
│
├── .github/              # 🔄 CI/CD workflows
│   └── workflows/
│       ├── connectx-test.yml
│       ├── ai-assistant-test.yml
│       ├── deploy-ai-assistant-dev.yml
│       ├── deploy-ai-assistant-prod.yml
│       ├── deploy-weaviate.yml
│       └── _deploy-ai-assistant.yml  # Reusable deploy workflow
│
└── .devcontainer/        # 🐳 VS Code Dev Container
    ├── devcontainer.json
    ├── post-create.sh
    └── Dockerfile
```

## 🚀 Quick Start

### Prerequisites

- **For Mobile App**: Flutter SDK (^3.9.2+), iOS/Android device
- **For Backend**: Python 3.14+, Docker, Google Cloud account, Gemini API key
- **Git LFS**: required to pull bundled ML model weights (see below)

### 0. Clone with Git LFS

This repo uses [Git LFS](https://git-lfs.com) to store the cross-encoder model weights (~87 MB).
Install LFS once and pull the files after cloning:

```bash
# Install (macOS)
brew install git-lfs
git lfs install          # registers LFS hooks globally (run once per machine)

# After cloning the repo
git lfs pull             # downloads model.safetensors and any other LFS-tracked files
```

If you skip `git lfs pull`, the `model.safetensors` file will be a 134-byte pointer and the
backend will fall back to downloading the model from HuggingFace Hub at first startup.

> **First-time setup without LFS access**: run `python ai-assistant/scripts/download_models.py`
> to download the model files directly from HuggingFace Hub into `ai-assistant/models/`.

### 1. Start the Backend Server

```bash
cd ai-assistant

# Copy and configure environment
cp .env.template .env
# Edit .env with your credentials

# Start with Docker
docker-compose up ai-assistant

# Server starts on localhost:8080
```

**See**: [AI-Assistant Documentation](docs/ai-assistant.md) for detailed setup.

### 2. Run the Mobile App

```bash
cd connectx

# Install dependencies
flutter pub get

# Configure environment
cp .env.template .env
# Edit .env with server URL

# Android: --flavor selects the Firebase project (Gradle); backend is set in .env
flutter run --flavor liteDev
# Other Android variants:
# flutter run --flavor liteProd
# flutter run --flavor fullDev
# flutter run --flavor fullProd

# iOS: --flavor requires matching Xcode schemes; omit unless configured
flutter run -d ios
```

**See**: [ConnectX Documentation](docs/connectx.md) for detailed setup including Firebase configuration.

### 3. Start Weaviate (full mode only)

The default **full mode** requires Weaviate for provider vector search. Skip this step if running in [lite mode](#deployment-modes).

```bash
# Start Weaviate
cd weaviate
docker-compose up -d

# Initialize database
cd ../ai-assistant
python scripts/init_database.py --load-test-data

```

**See**: [Weaviate Documentation](docs/weaviate.md) for detailed configuration.

## 🚀 Deployment Modes

Linkora ships two deployment profiles, selected via the `AGENT_MODE` environment
variable:

| | Full mode (`AGENT_MODE=full`, default) | Lite mode (`AGENT_MODE=lite`) |
|---|---|---|
| **Provider search** | Weaviate vector / hybrid search | Google Places API → cross-encoder |
| **Voice** | Yes (WebRTC audio) | Text-only |
| **Firestore** | Full read/write | Not used |
| **Provider onboarding** | Full flow | Not available |
| **Infrastructure** | Cloud Run + Weaviate VM | Cloud Run only |
| **Key env vars** | `WEAVIATE_URL` | `GOOGLE_PLACES_API_KEY` |

**Lite mode** is ideal for prototypes, demos, or regions where you don't yet have
providers registered in Weaviate.  The assistant fetches live results from the
Google Places API, enriches them with web crawling (skills, email, portfolio),
reranks them with a local cross-encoder model, and presents them to the user —
all without any Weaviate dependency.

See [Deployment Documentation](docs/deployment.md) for provisioning instructions
for both modes.

## 🧪 Testing

### Backend Tests
```bash
cd ai-assistant
pytest
pytest --cov=src tests/  # With coverage
```

### Frontend Tests

> **Note**: Only the **Android** version of the Flutter app has been properly tested. iOS builds are configured but have not been fully validated.

```bash
cd connectx
flutter test
```

## 🚀 Deployment

### Development
- Docker Compose for local development
- See [Getting Started Guide](docs/getting-started.md)

### Production
- Cloud Run (AI-Assistant) + Compute Engine VM (Weaviate)
- GitHub Actions for CI/CD

**See**: [Deployment Documentation](docs/deployment.md)

## 🔧 CI/CD & DevContainer

### GitHub Actions Workflows

The project includes automated CI/CD pipelines:

| File | Name | Purpose |
|---|---|---|
| `connectx-test.yml` | Flutter Tests | Builds devcontainer and runs Flutter tests |
| `ai-assistant-test.yml` | AI Assistant Tests | Lints, type-checks, and runs Python backend tests |
| `deploy-ai-assistant-dev.yml` | Deploy AI-Assistant (Dev) | Deploys to Cloud Run dev environment |
| `deploy-ai-assistant-prod.yml` | Deploy AI-Assistant (Prod) | Deploys to Cloud Run prod environment |
| `deploy-weaviate.yml` | Deploy Weaviate | Deploys Weaviate to Compute Engine VM |
| `_deploy-ai-assistant.yml` | Deploy AI-Assistant (Reusable) | Shared reusable workflow called by dev/prod deployers |

### DevContainer Cache & Rebuild

To speed up CI builds, we cache the devcontainer image. Here's how to manage it:

#### Normal Builds (Uses Cache)
Automatic - no action needed. The CI will use cached layers to speed up builds (1-2 min instead of 10 min).

#### Force Rebuild from Scratch

**Option 1: Manual Workflow Trigger (Recommended)**
1. Go to GitHub → Actions tab
2. Select "Build & Test ConnectX APK" or "Build and Cache DevContainer"
3. Click "Run workflow"
4. Check ✅ **"Force rebuild without cache"**
5. Click "Run workflow"

**Option 2: Commit Message Trigger**
Include `[rebuild]` or `[no-cache]` in your commit message:
```bash
git commit -m "Update dependencies [rebuild]"
git push
```

**Option 3: Delete Cache via GitHub CLI**
```bash
gh cache delete devcontainer-cache --repo Fides-Connect/linkora
```

**Option 4: GitHub UI**
1. Go to your repo → Settings → Actions → Caches
2. Find and delete the devcontainer cache

#### When to Force Rebuild?
- After major Dockerfile changes
- When cache corruption is suspected
- After updating system dependencies (Java, Android SDK, etc.)
- To verify a clean build without cached layers