# ConnectX - Mobile Application

ConnectX is the Flutter-based mobile application for the Linkora AI Voice Assistant platform, providing real-time voice interaction capabilities on iOS and Android devices.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)
- [Building for Production](#building-for-production)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

ConnectX is a comprehensive mobile client for the Linkora platform that:
- Captures user voice input via microphone
- Streams audio to AI-Assistant server via WebRTC
- Receives and plays AI-generated voice responses
- Manages user authentication with Firebase
- Provides a rich UI for managing service requests, favorites, and user profiles
- Displays detailed provider competencies and reviews

### Architecture

```
┌─────────────────────────────────────┐
│         ConnectX App                │
├─────────────────────────────────────┤
│  Presentation Layer (MVVM)          │
│  ├── Pages (Views)                  │
│  │   ├── Home (Requests)            │
│  │   ├── Favorites                  │
│  │   ├── User Profile               │
│  │   └── Menu                       │
│  ├── ViewModels (State Mgmt)        │
│  └── Widgets                        │
├─────────────────────────────────────┤
│  Data Layer                         │
│  ├── Repositories                   │
│  └── Data Sources (API/Mock)        │
├─────────────────────────────────────┤
│  Service Layer                      │
│  ├── ApiService                     │
│  ├── AuthService                    │
│  ├── WebRTCService                  │
│  ├── SpeechService                  │
│  ├── NotificationService            │
│  └── UserService                    │
├─────────────────────────────────────┤
│  WebRTC Layer                       │
│  └── flutter_webrtc                 │
├─────────────────────────────────────┤
│  Authentication Layer               │
│  └── Firebase Auth                  │
└─────────────────────────────────────┘
         ↕ WebRTC Audio Stream
┌─────────────────────────────────────┐
│      AI-Assistant Server            │
└─────────────────────────────────────┘
```

## ✨ Features

- **Voice Input**: Real-time audio capture and streaming
- **Voice Output**: Playback of AI-generated responses
- **Authentication**: Google Sign-In, Email/Password, Phone Auth
- **User Profile Sync**: Auto-syncs name, email, and photo from Google Profile to backend
- **Service Requests**: View and manage incoming/outgoing requests with role-based status labels
- **Favorites Management**: Save preferred providers for quick access
- **User Profiles**: Detailed view of users including location, competencies, and reviews
- **WebRTC**: Direct peer-to-peer audio streaming
- **Visual Feedback**: Audio visualization during recording
- **Chat History**: Conversation transcript display
- **Push Notifications**: FCM-based notifications for service-request status changes, in the user's configured language
- **App Settings**: Language (EN/DE) and notification-toggle preferences synced to the backend on login and saved persistently
- **Cross-Platform**: Runs on iOS and Android
- **Responsive UI**: Adaptive layout for different screen sizes

## 📋 Prerequisites

### Development Tools
- **Flutter SDK**: 3.9.2 or higher
- **Dart SDK**: Included with Flutter
- **IDE**: VS Code or Android Studio with Flutter plugin

### Platform-Specific Requirements

**For iOS Development:**
- macOS with Xcode 14.0+
- CocoaPods
- iOS device or simulator (iOS 12.0+)

**For Android Development:**
- Android Studio or Android SDK
- Java Development Kit (JDK 11+)
- Android device or emulator (API 21+)

### External Services
- Running AI-Assistant server (see [AI-Assistant Documentation](ai-assistant.md))
- Firebase project with Authentication enabled

## 🚀 Installation

### Step 1: Install Dependencies

```bash
cd connectx
flutter pub get
```

### Step 2: Firebase Configuration

#### Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Click "Add project" or select existing Google Cloud project
3. Complete Firebase setup wizard

> **Important**: Use the same Google Cloud project as your AI-Assistant backend for seamless token validation.

#### Enable Authentication Methods

1. In Firebase Console → Authentication → Sign-in method
2. Enable desired methods:
   - **Google**: Enable and add support email
   - **Email/Password**: Enable
   - **Phone**: Enable and configure reCAPTCHA

#### Configure OAuth Client

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to APIs & Services → Credentials
3. Create OAuth 2.0 Client ID:
   - Type: Web application
   - Authorized redirect URIs: `http://localhost:60099`
4. Copy the Client ID (format: `XXXXXXXX-XXXXXXXX.apps.googleusercontent.com`)

#### Run FlutterFire Configure

```bash
# Install FlutterFire CLI if not already installed
dart pub global activate flutterfire_cli

# Configure Firebase for your platforms
flutterfire configure --project=<your-project-id>

# Select platforms: android, ios, web
# This generates lib/firebase_options.dart
```

#### Android Setup

**Add SHA-1 Fingerprint:**

```bash
# Get debug keystore SHA-1
keytool -list -v -alias androiddebugkey \
  -keystore ~/.android/debug.keystore \
  -storepass android -keypass android | grep SHA1
```

Then:
1. Copy the SHA-1 fingerprint
2. In Firebase Console → Project Settings → Your apps → Android app
3. Click "Add fingerprint"
4. Paste SHA-1 and save

**Download google-services.json:**

1. In Firebase Console → Project Settings → Your apps
2. Find Android app (`com.linkora.connectx`)
3. Download `google-services.json`
4. Place it once per environment:
   - Dev: `connectx/android/app/src/dev/google-services.json`
   - Prod: `connectx/android/app/src/prod/google-services.json`

#### iOS Setup

**Download GoogleService-Info.plist:**

1. In Firebase Console → Project Settings → Your apps
2. If no iOS app exists yet, click **Add app → Apple (iOS+)** and register bundle ID `com.linkora.connectx`
3. Download `GoogleService-Info.plist`
4. Place it at `connectx/ios/Runner/GoogleService-Info.plist`

> **Note**: Unlike Android, iOS does not use per-flavor config files — a single `GoogleService-Info.plist` covers both dev and prod builds. The file is not checked in; each developer downloads it directly from the Firebase Console.

**CocoaPods:**

After placing the plist, run CocoaPods to install the native Firebase SDKs:

```bash
cd ios
pod install
cd ..
```

Open the workspace (not the `.xcodeproj`) in Xcode when doing native iOS development:

```bash
open ios/Runner.xcworkspace
```

**Microphone Permission:**

The app requires microphone access for voice input. The usage description is already defined in `ios/Runner/Info.plist`. No additional changes are needed unless you customise the permission message.

### Step 3: Environment Configuration

```bash
# Copy template
cp .env.template .env

# Edit configuration
nano .env
```

**Required Environment Variables:**

```properties
# AI-Assistant Server URL (without ws:// prefix or /ws suffix)
# Local development (use your machine's IP for Android emulator):
AI_ASSISTANT_SERVER_URL=192.168.1.100:8080

# Production deployment:
# AI_ASSISTANT_SERVER_URL=your-server-domain.com:8080

# Google OAuth Client ID (from Firebase setup)
GOOGLE_OAUTH_CLIENT_ID=XXXXXXXX-XXXXXXXX.apps.googleusercontent.com

# Web Port (must match OAuth redirect URI)
WEB_PORT=60099
```

> **Android Emulator Note**: Use your computer's network IP (e.g., `192.168.1.100`), NOT `localhost`, because the Android emulator runs in a separate network namespace.

## 📁 Project Structure

```
connectx/
├── lib/
│   ├── main.dart                      # App entry point
│   ├── firebase_options.dart          # Firebase configuration
│   ├── theme.dart                     # App theme and styling
│   │
│   ├── core/                          # Core utilities & widgets
│   │   ├── providers/                 # Global providers (UserProvider)
│   │   └── widgets/                   # Shared widgets (AppBackground)
│   │
│   ├── features/                      # Feature-based organization
│   │   ├── auth/                      # Authentication feature
│   │       └── presentation/
│   │   └── home/                      # Main Home feature
│   │       ├── data/                  # Repositories & Mock Data
│   │       │   └── repositories/
│   │       └── presentation/
│   │           ├── pages/             # App Pages (Tabs & Detail Views)
│   │           │   ├── home_tab_page.dart
│   │           │   ├── favorites_tab_page.dart
│   │           │   ├── menu_tab_page.dart
│   │           │   ├── request_detail_page.dart
│   │           │   └── user_detail_page.dart
│   │           │   └── user_page.dart
│   │           └── viewmodels/        # HomeTab & Search ViewModels
│   │
│   ├── models/                        # Data models
│   │   ├── chat_message.dart          # Chat message model
│   │   ├── user.dart                  # User & favorites model
│   │   ├── service_request.dart       # Service request model
│   │   └── competence.dart            # Competence model
│   │
│   ├── services/                      # Business logic
│   │   ├── api_service.dart           # HTTP client (GET/POST/PATCH/DELETE)
│   │   ├── auth_service.dart          # Firebase authentication
│   │   ├── notification_service.dart  # FCM notifications + toggle persistence
│   │   ├── speech_service.dart        # Speech recognition
│   │   ├── webrtc_service.dart        # WebRTC management
│   │   └── user_service.dart          # User profile & settings (singleton)
│   │
│   ├── utils/                         # Helper methods
│   │   └── constants.dart             # App constants
│   │
│   └── localization/                  # Internationalization (EN, DE)
│       ├── app_localizations.dart     # AppLocalizations facade
│       ├── messages_en.dart           # English strings
│       └── messages_de.dart           # German strings
│
├── android/                           # Android platform files
│   ├── app/
│   │   ├── build.gradle.kts
│   │   └── src/
│   │       ├── dev/google-services.json       # Firebase config (dev)
│   │       ├── prod/google-services.json      # Firebase config (prod)
│   │       ├── lite/                          # Lite-mode manifest/resources
│   │       └── full/                          # Full-mode manifest/resources
│   └── build.gradle.kts
│
├── ios/                               # iOS platform files
│   ├── Runner/
│   │   └── Info.plist
│   └── Runner.xcodeproj/
│
├── test/                              # Unit and widget tests
│   └── widget_test.dart
│
├── pubspec.yaml                       # Dependencies
├── .env                               # Environment variables
└── README.md                          # This file
```

## 🛠️ Development

### Build Flavors

The app uses two Gradle flavor dimensions to form four variants:

| Variant | Mode | Environment | Firebase project | Recommended backend |
|---|---|---|---|---|
| `liteDev` | lite (text-only, Google Places) | dev | `linkora-dev` | dev Cloud Run |
| `liteProd` | lite | prod | `linkora-prod` | prod Cloud Run |
| `fullDev` | full (voice + WebRTC) | dev | `linkora-dev` | dev Cloud Run |
| `fullProd` | full | prod | `linkora-prod` | prod Cloud Run |

> `--flavor` selects a full build variant combining both **mode** (`lite`/`full`) and **environment** (`dev`/`prod`):
> - The **environment** dimension determines which Firebase project (`google-services.json`) is used.
> - The **mode** dimension controls Android packaging — e.g. `full` includes the microphone permission; `lite` does not.
>
> `APP_MODE` and `AI_ASSISTANT_SERVER_URL` are still set via `.env` and can be changed for local development. For release builds, keep `APP_MODE` consistent with the selected mode flavor (`lite` or `full`) so runtime features match the permissions and resources bundled into the APK.

The `google-services.json` is shared between `lite` and `full` variants of the same environment. Place one file per environment in the `environment` source set:
- `android/app/src/dev/google-services.json` — used by both `liteDev` and `fullDev`
- `android/app/src/prod/google-services.json` — used by both `liteProd` and `fullProd`

Gradle resolves the environment source set (`src/dev/` or `src/prod/`) from the variant's environment dimension, and the mode source set (`src/lite/` or `src/full/`) from the mode dimension. Because dev and prod use different Firebase projects (`linkora-dev` and `linkora-prod`), do **not** place a single shared file at `android/app/google-services.json`. Re-download the file from Firebase Console whenever SHA-1 fingerprints change.

### Running the App

**On Connected Device:**
```bash
flutter run --flavor liteDev
```

**On Specific Device:**
```bash
# List devices
flutter devices

# Run on specific device
flutter run --flavor liteDev -d <device-id>
```

**Platform-Specific:**
```bash
# Android (flavors are Android/Gradle-only)
flutter run --flavor liteDev -d android

# iOS (no flavor required — single Firebase project per scheme)
flutter run -d ios

# Web (flavors not supported on web)
flutter run -d chrome
```

Replace `liteDev` with `liteProd`, `fullDev`, or `fullProd` as needed.

### Hot Reload

During development, use hot reload for instant updates:
- Press `r` in terminal for hot reload
- Press `R` for hot restart
- Press `q` to quit

### Key Services

#### AuthService

Handles Firebase authentication:

```dart
class AuthService {
  Future<User?> signInWithGoogle();
  Future<User?> signInWithEmail(String email, String password);
  Future<void> signOut();
  Stream<User?> get authStateChanges;
}
```

#### PeerConnectionHandler

Manages WebRTC connections:

```dart
class PeerConnectionHandler {
  Future<void> initialize();
  Future<void> createOffer();
  Future<void> handleAnswer(String sdp);
  Future<void> addIceCandidate(String candidate);
  void startAudioStreaming();
  void stopAudioStreaming();
}
```

#### SignalingService

WebSocket communication with server:

```dart
class SignalingService {
  Future<void> connect(String url);
  void sendMessage(Map<String, dynamic> message);
  Stream<Map<String, dynamic>> get messages;
  void disconnect();
}
```

### WebRTC Implementation

**Connection Flow:**

```dart
// 1. Initialize peer connection
await peerConnectionHandler.initialize();

// 2. Connect to signaling server
await signalingService.connect(serverUrl);

// 3. Create and send offer
final offer = await peerConnectionHandler.createOffer();
signalingService.sendMessage({
  'type': 'offer',
  'sdp': offer.sdp,
});

// 4. Receive answer
signalingService.messages.listen((message) {
  if (message['type'] == 'answer') {
    peerConnectionHandler.handleAnswer(message['sdp']);
  }
});

// 5. Start audio streaming
peerConnectionHandler.startAudioStreaming();
```

## 🧪 Testing

### Run All Tests

```bash
flutter test
```

### Run Specific Test

```bash
flutter test test/widget_test.dart
```

### Test Coverage

```bash
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```

### Widget Testing Example

```dart
testWidgets('MicButton shows recording state', (WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: MicButton(
          isRecording: true,
          onPressed: () {},
        ),
      ),
    ),
  );

  expect(find.byIcon(Icons.stop), findsOneWidget);
});
```

## 📦 Building for Production

### App Flavors

The app uses two Android product flavors that control which permissions are declared:

| Flavor | `RECORD_AUDIO` permission | Use case |
|--------|--------------------------|----------|
| `lite` | ✗ Not included | Text-only deployment (lite-mode server) |
| `full` | ✓ Included | Full voice + text deployment |

Set `APP_MODE` in `connectx/.env` to match the flavor before building:
```properties
# For lite builds
APP_MODE=lite
AI_ASSISTANT_SERVER_URL=https://your-lite-cloud-run-url.run.app

# For full builds
APP_MODE=full
AI_ASSISTANT_SERVER_URL=https://your-full-cloud-run-url.run.app
```

### Android Release Signing

Create `android/key.properties` (gitignored — never commit this file):
```properties
storePassword=YOUR_KEYSTORE_PASSWORD
keyPassword=YOUR_KEY_PASSWORD
keyAlias=YOUR_KEY_ALIAS
storeFile=../app/release.keystore
```

Place `release.keystore` at `android/app/release.keystore`.

### Android Release Build

```bash
# Lite mode — no microphone permission (text-only, Google Play)
flutter build appbundle --flavor liteProd --release
# Output: build/app/outputs/bundle/liteProdRelease/app-liteProd-release.aab

# Full mode — microphone permission included (voice + text, Google Play)
flutter build appbundle --flavor fullProd --release
# Output: build/app/outputs/bundle/fullProdRelease/app-fullProd-release.aab

# APK variants (for direct installation / testing)
flutter build apk --flavor liteProd --release
flutter build apk --flavor fullProd --release
```

### iOS Release Build

```bash
# Build for iOS
flutter build ios --release

# Archive in Xcode
open ios/Runner.xcworkspace
# Product → Archive → Distribute App
```

**iOS Signing:**
- Configure signing in Xcode
- Select appropriate provisioning profile
- Set up App Store Connect

## 🐛 Troubleshooting

### Common Issues

#### Firebase Authentication Fails

**Symptoms**: "Developer console not set up correctly" error

**Solution**:
1. Verify SHA-1 fingerprint added to Firebase Console
2. Check `GOOGLE_OAUTH_CLIENT_ID` in `.env`
3. Ensure `google-services.json` is in correct location
4. Verify Firebase project matches backend

#### WebRTC Connection Failed

**Symptoms**: No audio streaming, connection timeout

**Solution**:
1. Check `AI_ASSISTANT_SERVER_URL` in `.env`
2. For Android emulator, use machine IP, not `localhost`
3. Verify AI-Assistant server is running: `curl http://<server>:8080/health`
4. Check firewall rules and network connectivity
5. Review server logs for connection errors

#### Build Fails on iOS

**Symptoms**: CocoaPods errors, signing issues

**Solution**:
```bash
cd ios
pod deintegrate
pod install
cd ..
flutter clean
flutter pub get
flutter build ios
```

#### Audio Not Working

**Symptoms**: Microphone permission denied, no audio playback

**Solution**:
1. Verify microphone permissions granted in device settings
2. Check `Info.plist` contains microphone usage description
3. Restart app after granting permissions
4. Test with different audio input/output devices

#### Hot Reload Not Working

**Symptoms**: Changes not reflected after hot reload

**Solution**:
- Use hot restart (`R`) instead of hot reload (`r`)
- Some changes require full rebuild:
  - Native code changes
  - Asset changes
  - Dependency changes

### Debug Mode

Enable detailed logging:

```dart
// In main.dart
void main() {
  // Enable verbose logging
  Logger.root.level = Level.ALL;
  Logger.root.onRecord.listen((record) {
    print('${record.level.name}: ${record.time}: ${record.message}');
  });
  
  runApp(MyApp());
}
```

### Performance Profiling

```bash
# Run with performance overlay
flutter run --flavor liteDev --profile

# Open DevTools
flutter pub global activate devtools
flutter pub global run devtools
```

## 📱 Platform-Specific Notes

### iOS Considerations

- **Minimum Version**: iOS 12.0+
- **Permissions**: Microphone access required
- **Background Audio**: Requires background modes capability
- **App Transport Security**: Configure for non-HTTPS servers in development

### Android Considerations

- **Minimum SDK**: API 21 (Android 5.0)
- **Permissions**: Microphone, internet
- **ProGuard**: Configure rules for release builds
- **Network Security**: Allow cleartext traffic in development

## 🚀 Best Practices

### Code Organization

- Keep widgets small and focused
- Extract reusable components
- Use services for business logic
- Implement proper error handling

### State Management

- Use Provider for app-wide state
- Keep local state in StatefulWidget when appropriate
- Avoid unnecessary rebuilds

### Performance

- Dispose controllers and streams properly
- Use `const` constructors where possible
- Implement lazy loading for large lists
- Profile regularly to identify bottlenecks

### Security

- Never commit `.env` file
- Use secure storage for sensitive data
- Validate all user inputs
- Keep dependencies updated

## 🔗 Related Documentation

- [Getting Started Guide](getting-started.md) - Initial setup
- [AI-Assistant Documentation](ai-assistant.md) - Backend server
- [Architecture Overview](architecture.md) - System design
