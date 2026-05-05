<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="connectx/assets/images/LinkoraLogo.png">
    <img src="connectx/assets/images/LinkoraLogoDark.png" alt="Linkora" width="280">
  </picture>
</p>

<p align="center">
  <strong>AI-powered service marketplace assistant. Voice &amp; chat, end-to-end open source.</strong>
</p>

<p align="center">
    <img src="https://img.shields.io/github/actions/workflow/status/Fides-Connect/linkora/connectx-test.yml?branch=main&label=ConnectX%20Tests&logo=flutter&style=for-the-badge" alt="ConnectX Build Status">
    <img src="https://img.shields.io/github/actions/workflow/status/Fides-Connect/linkora/ai-assistant-test.yml?branch=main&label=AI%20Assistant%20Tests&logo=python&style=for-the-badge" alt="AI Assistant Build Status">
    <img src="https://img.shields.io/github/license/Fides-Connect/linkora?style=for-the-badge" alt="License">
</p>

<p align="center">
  <a href="docs/getting-started.md">Getting Started</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/connectx.md">Mobile App</a> ·
  <a href="docs/ai-assistant.md">Backend</a> ·
  <a href="docs/deployment.md">Deployment</a>
</p>

---

Linkora is a production-ready platform that lets users find local service providers through a **natural conversation** by voice or text. The AI assistant (named **Elin**) guides the user, collects requirements, and returns ranked, enriched provider results. Developers get a complete, deployable stack: a Flutter mobile app, a Python WebRTC server and a vector database, all wired together and ready to customise.

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
      <sub>AI-curated provider cards with contact &amp; request actions (results anonymized)</sub>
    </td>
  </tr>
</table>

## ✨ Features

- 🎙️ **Voice-first UX**: Real-time WebRTC audio streaming with Google STT/TTS for sub-second round-trips.
- 🤖 **Conversational Search**: The AI assistant, Elin, asks clarifying questions, extracts structured intent, and performs a semantic search.
- 🔀 **Two Deployment Modes**:
    - **Full**: Utilizes a Weaviate vector database with onboarded providers for deep semantic search.
    - **Lite**: Operates with zero infrastructure using Google Places and web enrichment.
- 🔒 **Secure by Design**: All API keys are kept server-side, and clients authenticate via Firebase for enhanced security.
- 📦 **Batteries Included**: Comes with Docker Compose, Cloud Run deployment scripts, GitHub Actions for CI/CD, and a dev container for a seamless development experience.
- 🧪 **Well-Tested**: A comprehensive suite of over 60 backend unit tests, Flutter widget tests, and coverage reporting ensures reliability.

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Mobile App** | ![Flutter](https://img.shields.io/badge/Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white) ![Dart](https://img.shields.io/badge/Dart-0175C2?style=for-the-badge&logo=dart&logoColor=white) |
| **AI Backend** | ![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![aiohttp](https://img.shields.io/badge/aiohttp-2C5BB4?style=for-the-badge&logo=python&logoColor=white) ![Google Cloud](https://img.shields.io/badge/Google%20Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white) ![WebRTC](https://img.shields.io/badge/WebRTC-333333?style=for-the-badge&logo=webrtc&logoColor=white) |
| **Database** | ![Weaviate](https://img.shields.io/badge/Weaviate-0C9E73?style=for-the-badge&logo=weaviate&logoColor=white) ![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=for-the-badge&logo=firebase&logoColor=black) |
| **DevOps** | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white) ![Cloud Run](https://img.shields.io/badge/Cloud%20Run-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white) |

## 🏗️ Platform Overview

```mermaid
graph TD
    subgraph "User's Device"
        A[ConnectX Mobile App <br><i>Flutter</i>]
    end

    subgraph "Shared Infrastructure"
        B[AI Assistant <br><i>Python / aiohttp</i>]
        D[Firebase <br><i>Auth & Firestore</i>]
    end

    subgraph "Full Mode only"
        C[Weaviate <br><i>Vector Database</i>]
        E[Google Cloud <br><i>STT / TTS</i>]
    end

    subgraph "Lite Mode only"
        F[Google Places API]
    end

    A -- "Authentication" --> D
    A -- "WebRTC Audio" --> B
    A -- "Text chat" --> B
    B -- "User Data" --> D
    B -- "Semantic Search" --> C
    B -- "Speech Services" --> E
    B -- "Places Search" --> F

    style A fill:#02569B,stroke:#333,stroke-width:2px,color:#fff
    style B fill:#3776AB,stroke:#333,stroke-width:2px,color:#fff
    style C fill:#0C9E73,stroke:#333,stroke-width:2px,color:#fff
    style D fill:#FFCA28,stroke:#333,stroke-width:2px,color:#000
    style E fill:#4285F4,stroke:#333,stroke-width:2px,color:#fff
    style F fill:#34A853,stroke:#333,stroke-width:2px,color:#fff
```
**Read more**: [Architecture Overview](docs/architecture.md)

## 🚀 Getting Started

### Prerequisites
- [Flutter SDK](https://flutter.dev/docs/get-started/install)
- [Python 3.14+](https://www.python.org/downloads/)
- [Docker](https://www.docker.com/products/docker-desktop/)
- [Firebase Account](https://firebase.google.com/)

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/Fides-Connect/linkora.git
    cd linkora
    ```

2.  **Setup AI Assistant (Backend):**
    ```sh
    cd ai-assistant
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    ```
    Then copy and configure the environment file — the backend will not start without `GEMINI_API_KEY` and Firebase Admin credentials:
    ```sh
    cp .env.template .env
    # Edit .env with your credentials
    ```
    See the [AI Assistant docs](docs/ai-assistant.md) for the full list of required variables.

3.  **Setup ConnectX (Mobile App):**
    ```sh
    cd connectx
    flutter pub get
    cp .env.template .env
    # Edit .env — set APP_MODE, AI_ASSISTANT_SERVER_URL, GOOGLE_OAUTH_CLIENT_ID
    ```
    The app also requires Firebase config files (not checked in). Run `flutterfire configure` from the `connectx` directory and add the generated native files (`google-services.json` for Android, `GoogleService-Info.plist` for iOS). See the [ConnectX docs](docs/connectx.md) for details.

4.  **Launch and initialize Weaviate (Full mode only):**
    ```sh
    cd ../weaviate
    docker-compose up -d
    ```
    > Starting the container brings up an empty database. Complete the schema and sample-data initialization from the [Getting Started Guide](docs/getting-started.md) before using Full mode — there will be nothing to search against otherwise.

5.  **Run the application:**
    - Start the AI Assistant backend (from the `ai-assistant` directory).
    - Launch the Flutter app with the required build flavor (Android):
      ```sh
      flutter run --flavor liteDev   # or fullDev, liteProd, fullProd
      ```

For full setup instructions including Firebase configuration and Weaviate initialization, see the [Getting Started Guide](docs/getting-started.md).

## 📁 Repository Structure

```
linkora/
├── docs/                 # 📖 Comprehensive documentation for architecture, setup, and deployment.
├── connectx/             # 📱 Flutter mobile application for iOS and Android.
├── ai-assistant/         # 🤖 Python-based AI backend with aiohttp and WebRTC.
├── weaviate/             # 🗃️ Docker configuration for the Weaviate vector database.
└── .github/              # ⚙️ GitHub Actions for CI/CD workflows.
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue to discuss your ideas.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


