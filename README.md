# Flutter Development Container

A complete Flutter development environment using Docker and VS Code Dev Containers, optimized for Apple Silicon Macs.

## 🚀 Features

- **Flutter SDK**: Latest stable version with all platforms enabled
- **Android SDK**: Complete Android development setup with emulator support
- **Cross-platform**: Support for iOS, Android, Web, and Desktop development
- **Device Testing**: USB debugging support for physical devices
- **VS Code Integration**: Pre-configured extensions and settings
- **Chrome Browser**: For Flutter web development and testing
- **Ubuntu 24.04**: Modern, stable base with ARM64 optimization

## 📋 Prerequisites

- **macOS** (preferably with Apple Silicon)
- **Docker Desktop** (latest version)
- **VS Code** with Dev Containers extension
- **8GB+ RAM** recommended (16GB+ for smooth emulator performance)

## 🏗️ Setup Instructions

### 1. Clone/Download this Repository

```bash
git clone <Fides-repo>
cd Fides
```

### 2. Open in VS Code

```bash
code .
```

### 3. Start Dev Container

1. VS Code should prompt to "Reopen in Container" - click **Reopen in Container**
2. Or use Command Palette (`Cmd+Shift+P`) → **Dev Containers: Reopen in Container**
3. Wait for the container to build (first time takes 10-15 minutes)

### 4. Verify Setup

Once the container is ready, open a terminal and run:

```bash
flutter doctor -v
```

You should see all checkmarks ✅ for Flutter, Android toolchain, and other components.

## 📱 Development Workflows

### ⚙️ Environment Variables

Before running the project, copy and rename `template.env` to `.env` and add your actual environment variables:

```sh
cp connectx/template.env connectx/.env
```

Edit `.env` to set your values as needed.

### Generating an OAuth 2 Access Token

To generate an OAuth 2 access token using a Google Cloud service account JSON key file and write it directly to your `.env` file, run:

```sh
python scripts/generateOAuth2Token.py <service_account_json_path> <env_file_path>
```

**Required parameters:**
- `<service_account_json_path>`: Path to your Google Cloud service account JSON key file.
- `<env_file_path>`: Path to the `.env` file to update.

The script will write the generated token to the specified `.env` file as `OAUTH_ACCESS_TOKEN=<token>`.

> **Note:** The OAuth 2 token is only valid for 1 hour due to Google security guidelines. You will need to refresh/regenerate the token periodically.

Example:

```sh
python scripts/generateOAuth2Token.py /path/to/service-account.json connectx/.env
```

### Setting up a Python virtual environment (recommended)

Before running the script, create and activate a virtual environment and install dependencies from `requirements.txt`:

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

# Run the token generator
python scripts/generateOAuth2Token.py /path/to/service-account.json connectx/.env

# When finished
deactivate
```

### Running on Different Platforms

```bash
# Android Emulator
flutter run

# Web Browser
flutter run -d chrome

#or
flutter run -d web-server

# Linux Desktop (within container)
flutter run -d linux
```

### Device Testing

#### Physical Android Device

1. **Enable Developer Options** on your Android device:
   - Go to Settings → About Phone
   - Tap "Build Number" 7 times
   - Go back to Settings → Developer Options
   - Enable "USB Debugging"

2. **Connect Device**:
   ```bash
   # Check if device is detected
   adb devices
   
   # If device shows as unauthorized, check your phone for USB debugging prompt
   flutter devices
   
   # Run on connected device
   flutter run
   ```

#### iOS Device (Requires additional setup)

Note: iOS development requires Xcode and is limited when using containers. For full iOS development:

1. Use Xcode on your Mac for iOS builds
2. The container can be used for shared code development
3. Consider using VS Code on macOS directly for iOS projects

### Android Emulator

The container includes a pre-configured Android emulator:

```bash
# List available emulators
flutter emulators

# Launch emulator
flutter emulators --launch Flutter_Emulator

# Run app on emulator
flutter run
```

## 🔧 Useful Commands

### Flutter Commands
```bash
flutter doctor              # Check setup
flutter devices             # List available devices
flutter clean               # Clean build cache
flutter pub get             # Get dependencies
flutter pub upgrade         # Upgrade dependencies
flutter build apk           # Build APK for Android
flutter build web           # Build for web
```

### Android/ADB Commands
```bash
adb devices                 # List connected devices
adb kill-server             # Restart ADB server
adb start-server            # Start ADB server
adb logcat                  # View device logs
```

### Container Management
```bash
# Rebuild container (if you modify Dockerfile)
# Use Command Palette: "Dev Containers: Rebuild Container"

# View container logs
docker logs <container-id>
```

## 🛠️ Customization

### Adding VS Code Extensions

Edit `.devcontainer/devcontainer.json` and add extension IDs to the `extensions` array:

```json
"extensions": [
    "Dart-Code.dart-code",
    "Dart-Code.flutter",
    "your-extension-id"
]
```

### Installing Additional Tools

Edit `.devcontainer/Dockerfile` to add more packages:

```dockerfile
RUN apt-get update && apt-get install -y \
    your-package-name \
    && rm -rf /var/lib/apt/lists/*
```

### Environment Variables

Modify `.devcontainer/devcontainer.json` `containerEnv` section:

```json
"containerEnv": {
    "YOUR_VARIABLE": "your-value"
}
```

## 🚨 Troubleshooting

### Container Build Issues

1. **Permission Errors**:
   ```bash
   # Reset Docker Desktop
   # Or run with --privileged flag (already included)
   ```

2. **Slow Build**:
   - Ensure Docker Desktop has enough RAM allocated (8GB+)
   - Close other resource-intensive applications

### Flutter Doctor Issues

1. **Android License Issues**:
   ```bash
   flutter doctor --android-licenses
   ```

2. **Missing Platform Tools**:
   ```bash
   sdkmanager "platform-tools" "platforms;android-34"
   ```

### Device Connection Issues

1. **Android Device Not Detected**:
   ```bash
   # Restart ADB
   adb kill-server && adb start-server
   
   # Check USB connection and debugging permission
   adb devices
   ```

2. **Emulator Won't Start**:
   ```bash
   # Check available system images
   sdkmanager --list | grep system-images
   
   # Recreate AVD
   avdmanager delete avd -n Flutter_Emulator
   # Then restart container to recreate
   ```

### Performance Issues

1. **Slow Emulator**:
   - Increase Docker Desktop memory allocation
   - Use physical device for better performance
   - Consider using Genymotion or other lightweight emulators

2. **Hot Reload Not Working**:
   ```bash
   # Try running with verbose output
   flutter run -v
   
   # Clear Flutter cache
   flutter clean && flutter pub get
   ```

## 📖 Additional Resources

- [Flutter Documentation](https://docs.flutter.dev/)
- [Dart Language Tour](https://dart.dev/guides/language/language-tour)
- [Flutter Cookbook](https://docs.flutter.dev/cookbook)
- [Android Developer Docs](https://developer.android.com/)
- [VS Code Dev Containers](https://code.visualstudio.com/docs/remote/containers)

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Happy Flutter Development! 🎉**

