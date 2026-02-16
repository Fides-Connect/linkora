FROM ubuntu:24.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV FLUTTER_ROOT="/opt/flutter"
ENV ANDROID_HOME="/usr/lib/android-sdk"
ENV ANDROID_SDK_ROOT="/usr/lib/android-sdk"
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
ENV PATH="$JAVA_HOME/bin:$FLUTTER_ROOT/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
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
    openjdk-21-jdk-headless \
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

# Set JAVA_HOME explicitly for Java 21
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
ENV PATH="$JAVA_HOME/bin:$PATH"

# Create directories with proper ownership
RUN mkdir -p $FLUTTER_ROOT $ANDROID_HOME \
    && chown -R vscode:vscode $FLUTTER_ROOT $ANDROID_HOME

# Switch to vscode user
USER vscode
WORKDIR /home/vscode

# Download and install Flutter SDK (minimal installation with shallow clone)
RUN git clone https://github.com/flutter/flutter.git -b stable --depth 1 $FLUTTER_ROOT \
    && $FLUTTER_ROOT/bin/flutter --version \
    && $FLUTTER_ROOT/bin/flutter config --no-analytics \
    && cd $FLUTTER_ROOT \
    && git gc --aggressive --prune=all

# Switch back to root for Android SDK installation (needs write access to /usr/lib)
USER root

# Download and install Android SDK (minimal)
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && cd $ANDROID_HOME \
    && wget -q -O sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
    && unzip -q sdk-tools.zip \
    && mv cmdline-tools latest \
    && mkdir cmdline-tools \
    && mv latest cmdline-tools/ \
    && rm sdk-tools.zip \
    && chown -R vscode:vscode $ANDROID_HOME

# Switch to vscode for SDK manager (it needs to write to user's .android folder)
USER vscode

# Accept licenses and install minimal Android SDK components
# Only install CMake which was shown in error log - NDK will be downloaded by Flutter if needed
RUN yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses || true \
    && $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager \
        "platform-tools" \
        "build-tools;34.0.0" \
        "platforms;android-34" \
        "cmdline-tools;latest" \
        "cmake;3.22.1"

# Clean up Android SDK unnecessary files
USER root
RUN rm -rf $ANDROID_HOME/emulator \
    && rm -rf $ANDROID_HOME/system-images \
    && rm -rf $ANDROID_HOME/.temp \
    && chown -R vscode:vscode $ANDROID_HOME

USER vscode

# Pre-download only essential Dart dependencies
RUN $FLUTTER_ROOT/bin/flutter precache --android --no-ios --no-web --no-linux --no-macos --no-windows --no-fuchsia \
    && rm -rf $FLUTTER_ROOT/.pub-cache/hosted/*/test || true \
    && rm -rf $FLUTTER_ROOT/.pub-cache/hosted/*/example || true

# Create workspace directory
RUN mkdir -p /home/vscode/workspace
WORKDIR /home/vscode/workspace

# Final environment setup
RUN echo 'export JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"' >> ~/.bashrc \
    && echo 'export PATH="$JAVA_HOME/bin:$FLUTTER_ROOT/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"' >> ~/.bashrc \
    && echo 'export ANDROID_HOME="$ANDROID_HOME"' >> ~/.bashrc \
    && echo 'export ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"' >> ~/.bashrc \
    && echo 'export CHROME_EXECUTABLE="/usr/bin/chromium-browser"' >> ~/.bashrc

# Expose common Flutter development ports
EXPOSE 8080 3000 5000 5001 8000 9000

# Keep container running for dev container use
CMD ["sleep", "infinity"]