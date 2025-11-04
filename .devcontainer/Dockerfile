FROM ubuntu:24.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV FLUTTER_ROOT="/opt/flutter"
ENV ANDROID_HOME="/usr/lib/android-sdk"
ENV ANDROID_SDK_ROOT="/usr/lib/android-sdk"
ENV PATH="$FLUTTER_ROOT/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
ENV CHROME_EXECUTABLE="/usr/bin/chromium-browser"

# Create vscode user with UID/GID 1001 to avoid conflicts
RUN groupadd --gid 1001 vscode \
    && useradd --uid 1001 --gid vscode --shell /bin/bash --create-home vscode \
    && apt-get update \
    && apt-get install -y sudo \
    && echo vscode ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

# Install system dependencies
RUN apt-get update && apt-get install -y \
    coreutils \
    util-linux \
    procps \
    curl \
    git \
    wget \
    unzip \
    xz-utils \
    zip \
    libglu1-mesa \
    openjdk-17-jdk \
    build-essential \
    libssl-dev \
    clang \
    cmake \
    ninja-build \
    pkg-config \
    libgtk-3-dev \
    liblzma-dev \
    libstdc++-12-dev \
    fonts-droid-fallback \
    ttf-wqy-zenhei \
    ssh \
    rsync \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    apt-transport-https \
    usbutils \
    android-tools-adb \
    android-tools-fastboot \
    android-sdk \
    google-android-platform-34-installer \
    python3-requests \
    python3-google-auth \
    python3-dotenv \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium for Flutter web development (ARM64 compatible)
RUN apt-get update \
    && apt-get install -y chromium-browser \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p $FLUTTER_ROOT $ANDROID_HOME
RUN chown -R vscode:vscode $FLUTTER_ROOT $ANDROID_HOME

# Switch to vscode user
USER vscode
WORKDIR /home/vscode

# Download and install Flutter SDK (latest stable version)
RUN git clone https://github.com/flutter/flutter.git -b stable $FLUTTER_ROOT \
    && $FLUTTER_ROOT/bin/flutter --version

# Download and install Android SDK
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && cd $ANDROID_HOME \
    && wget -O sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
    && unzip sdk-tools.zip \
    && mv cmdline-tools latest \
    && mkdir cmdline-tools \
    && mv latest cmdline-tools/ \
    && rm sdk-tools.zip

# Skip Android SDK components that require network access or have ARM64 compatibility issues
# The essential tools will be installed by Flutter when needed at runtime
RUN yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses || true

# Pre-download Dart dependencies and configure Flutter (skip Android components during build)
RUN $FLUTTER_ROOT/bin/flutter precache \
    && $FLUTTER_ROOT/bin/flutter config --enable-web \
    && $FLUTTER_ROOT/bin/flutter config --enable-linux-desktop \
    && $FLUTTER_ROOT/bin/flutter config --enable-macos-desktop \
    && $FLUTTER_ROOT/bin/flutter config --enable-windows-desktop

# Install additional useful tools
RUN curl -fsSL https://deno.land/x/install/install.sh | sh \
    && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

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