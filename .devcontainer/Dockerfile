FROM ubuntu:24.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV FLUTTER_ROOT="/opt/flutter"
ENV ANDROID_HOME="/usr/lib/android-sdk"
ENV ANDROID_SDK_ROOT="/usr/lib/android-sdk"
ENV PATH="$FLUTTER_ROOT/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
ENV CHROME_EXECUTABLE="/usr/bin/chromium-browser"
ENV PUB_CACHE="/home/vscode/.pub-cache"

# Create vscode user with UID/GID 1001 to avoid conflicts
RUN groupadd --gid 1001 vscode \
    && useradd --uid 1001 --gid vscode --shell /bin/bash --create-home vscode \
    && apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && echo vscode ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install system dependencies - minimize packages to essential only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    unzip \
    xz-utils \
    zip \
    openjdk-17-jdk-headless \
    clang \
    cmake \
    ninja-build \
    pkg-config \
    libgtk-3-dev \
    liblzma-dev \
    libstdc++-12-dev \
    ca-certificates \
    gnupg \
    android-sdk \
    google-android-platform-34-installer \
    chromium-browser \
    python3 \
    python3-venv \
    python-is-python3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/share/doc/* \
    && rm -rf /usr/share/man/* \
    && rm -rf /var/cache/apt/*

# Create directories
RUN mkdir -p $FLUTTER_ROOT $ANDROID_HOME
RUN chown -R vscode:vscode $FLUTTER_ROOT $ANDROID_HOME

# Switch to vscode user
USER vscode
WORKDIR /home/vscode

# Download and install Flutter SDK (minimal installation with shallow clone)
RUN git clone https://github.com/flutter/flutter.git -b stable --depth 1 $FLUTTER_ROOT \
    && $FLUTTER_ROOT/bin/flutter --version \
    && $FLUTTER_ROOT/bin/flutter config --no-analytics \
    && cd $FLUTTER_ROOT \
    && git gc --aggressive --prune=all

# Download and install Android SDK (minimal)
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && cd $ANDROID_HOME \
    && wget -q -O sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
    && unzip -q sdk-tools.zip \
    && mv cmdline-tools latest \
    && mkdir cmdline-tools \
    && mv latest cmdline-tools/ \
    && rm sdk-tools.zip

# Accept licenses and install minimal Android SDK components
RUN yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses || true \
    && $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager \
        "platform-tools" \
        "build-tools;34.0.0" \
        "platforms;android-34" \
        "cmdline-tools;latest" \
    && rm -rf $ANDROID_HOME/emulator \
    && rm -rf $ANDROID_HOME/system-images \
    && rm -rf $ANDROID_HOME/.temp

# Pre-download only essential Dart dependencies
RUN $FLUTTER_ROOT/bin/flutter precache --android --no-ios --no-web --no-linux --no-macos --no-windows --no-fuchsia \
    && rm -rf $FLUTTER_ROOT/.pub-cache/hosted/pub.dartlang.org/*/test \
    && rm -rf $FLUTTER_ROOT/.pub-cache/hosted/pub.dartlang.org/*/example

# Create workspace directory
RUN mkdir -p /home/vscode/workspace
WORKDIR /home/vscode/workspace

# Set proper permissions
USER root
RUN chown -R vscode:vscode /home/vscode \
    && chmod -R 755 /home/vscode

# Switch back to vscode user
USER vscode

# Final environment setup
RUN echo 'export PATH="$FLUTTER_ROOT/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"' >> ~/.bashrc \
    && echo 'export ANDROID_HOME="$ANDROID_HOME"' >> ~/.bashrc \
    && echo 'export ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"' >> ~/.bashrc \
    && echo 'export CHROME_EXECUTABLE="/usr/bin/chromium-browser"' >> ~/.bashrc

# Expose common Flutter development ports
EXPOSE 8080 3000 5000 5001 8000 9000

# Keep container running for dev container use
CMD ["sleep", "infinity"]