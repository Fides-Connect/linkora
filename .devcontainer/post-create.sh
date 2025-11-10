#!/bin/bash

# Create Python Virtual Environment and install dependencies
echo "🐍 Installing Python dependencies..."
python3 -m venv .venv
.venv/bin/pip install -r ./ai-assistant/requirements.txt
.venv/bin/pip install -r ./connectx/requirements.txt
echo "source /workspaces/Fides/.venv/bin/activate" >> ~/.bashrc

# Run Flutter doctor to check setup
echo "🔍 Running Flutter doctor..."
/opt/flutter/bin/flutter doctor -v

# Enable udev rules for Android devices (if running on Linux host)
echo "🔧 Setting up Android device debugging..."
sudo tee /etc/udev/rules.d/51-android.rules > /dev/null <<EOF
# Google
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"
# Samsung
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev"
# LG
SUBSYSTEM=="usb", ATTR{idVendor}=="1004", MODE="0666", GROUP="plugdev"
# Motorola
SUBSYSTEM=="usb", ATTR{idVendor}=="22b8", MODE="0666", GROUP="plugdev"
# Sony
SUBSYSTEM=="usb", ATTR{idVendor}=="0fce", MODE="0666", GROUP="plugdev"
# HTC
SUBSYSTEM=="usb", ATTR{idVendor}=="0bb4", MODE="0666", GROUP="plugdev"
# Huawei
SUBSYSTEM=="usb", ATTR{idVendor}=="12d1", MODE="0666", GROUP="plugdev"
# Xiaomi
SUBSYSTEM=="usb", ATTR{idVendor}=="2717", MODE="0666", GROUP="plugdev"
# OnePlus
SUBSYSTEM=="usb", ATTR{idVendor}=="2a70", MODE="0666", GROUP="plugdev"
EOF

sudo chmod a+r /etc/udev/rules.d/51-android.rules
sudo usermod -a -G plugdev vscode

# Add some useful dev dependencies
cd /workspaces/Fides/connectx
/opt/flutter/bin/flutter pub add dev:flutter_lints
/opt/flutter/bin/flutter pub add dev:test
/opt/flutter/bin/flutter pub get

# Create useful aliases
echo "📝 Setting up aliases..."
cat >> ~/.bashrc << 'EOF'

# Add dev-helper script to PATH
export PATH="/workspaces/Fides/scripts:$PATH"

# Flutter aliases
alias fl='flutter'
alias flr='flutter run'
alias flb='flutter build'
alias flc='flutter clean'
alias flpg='flutter pub get'
alias flpa='flutter pub add'
alias fld='flutter doctor'
alias fldr='flutter doctor -v'
alias flemu='flutter emulators'
alias fldev='flutter devices'

# Android aliases
alias adb-restart='adb kill-server && adb start-server'
alias emulator-list='emulator -list-avds'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline'
EOF

# Create AVD (Android Virtual Device) for testing
echo "📱 Creating Android Virtual Device..."
echo "no" | /usr/lib/android-sdk/cmdline-tools/latest/bin/avdmanager create avd \
    -n "Flutter_Emulator" \
    -k "system-images;android-34;google_apis_playstore;arm64-v8a" \
    -d "pixel_7_pro" \
    --force || true

echo "✅ Flutter development environment setup complete!"
echo ""
echo "🎉 Ready to develop Flutter apps!"
echo ""
echo "Quick commands:"
echo "  flutter doctor          - Check Flutter setup"
echo "  flutter devices         - List available devices"
echo "  flutter emulators       - List available emulators"
echo "  flutter create my_app   - Create new Flutter project"
echo "  flutter run             - Run Flutter app"
echo ""
echo "For physical device testing:"
echo "  1. Enable Developer Options and USB Debugging on your device"
echo "  2. Connect via USB"
echo "  3. Run: adb devices"
echo "  4. Accept USB debugging prompt on device"
echo ""
