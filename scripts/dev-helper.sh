#!/bin/bash

# Flutter Development Helper Scripts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to create a new Flutter project
create_flutter_project() {
    local project_name=$1
    if [ -z "$project_name" ]; then
        echo_error "Please provide a project name"
        echo "Usage: ./scripts/dev-helper.sh create my_app_name"
        return 1
    fi
    
    echo_info "Creating Flutter project: $project_name"
    flutter create "$project_name" --platforms=android,ios,web,linux,macos,windows
    cd "$project_name"
    
    echo_info "Adding common development dependencies..."
    flutter pub add dev:flutter_lints
    flutter pub add dev:test
    flutter pub add dev:build_runner
    flutter pub get
    
    echo_success "Flutter project '$project_name' created successfully!"
    echo_info "To run the project:"
    echo "  cd $project_name"
    echo "  flutter run"
}

# Function to setup Android emulator
setup_emulator() {
    echo_info "Setting up Android emulator..."
    
    # Kill any existing emulator processes
    pkill -f emulator || true
    
    # Create AVD if it doesn't exist
    if ! avdmanager list avd | grep -q "Flutter_Emulator"; then
        echo_info "Creating new Android Virtual Device..."
        echo "no" | avdmanager create avd \
            -n "Flutter_Emulator" \
            -k "system-images;android-34;google_apis_playstore;arm64-v8a" \
            -d "pixel_7_pro" \
            --force
        echo_success "Android Virtual Device created successfully!"
    else
        echo_success "Android Virtual Device already exists!"
    fi
}

# Function to start Android emulator
start_emulator() {
    echo_info "Starting Android emulator..."
    setup_emulator
    
    # Start emulator in background
    emulator -avd Flutter_Emulator -no-audio -no-window &
    
    echo_info "Waiting for emulator to boot..."
    adb wait-for-device
    echo_success "Android emulator is ready!"
}

# Function to check development environment
check_env() {
    echo_info "Checking Flutter development environment..."
    echo ""
    
    # Flutter doctor
    flutter doctor -v
    echo ""
    
    # List available devices
    echo_info "Available devices:"
    flutter devices
    echo ""
    
    # List available emulators
    echo_info "Available emulators:"
    flutter emulators
    echo ""
    
    # ADB devices
    echo_info "Connected ADB devices:"
    adb devices
}

# Function to clean Flutter project
clean_project() {
    local project_path=${1:-.}
    echo_info "Cleaning Flutter project at: $project_path"
    
    cd "$project_path"
    flutter clean
    flutter pub get
    
    echo_success "Project cleaned successfully!"
}

# Function to build APK
build_apk() {
    local project_path=${1:-.}
    echo_info "Building APK for project at: $project_path"
    
    cd "$project_path"
    flutter build apk --release
    
    if [ $? -eq 0 ]; then
        echo_success "APK built successfully!"
        echo_info "APK location: $project_path/build/app/outputs/flutter-apk/app-release.apk"
    else
        echo_error "APK build failed!"
        return 1
    fi
}

# Function to run tests
run_tests() {
    local project_path=${1:-.}
    echo_info "Running tests for project at: $project_path"
    
    cd "$project_path"
    flutter test
    
    if [ $? -eq 0 ]; then
        echo_success "All tests passed!"
    else
        echo_error "Some tests failed!"
        return 1
    fi
}

# Main script logic
case "$1" in
    "create")
        create_flutter_project "$2"
        ;;
    "emulator")
        start_emulator
        ;;
    "check")
        check_env
        ;;
    "clean")
        clean_project "$2"
        ;;
    "build")
        build_apk "$2"
        ;;
    "test")
        run_tests "$2"
        ;;
    *)
        echo "Flutter Development Helper"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  create <name>     Create a new Flutter project"
        echo "  emulator          Start Android emulator"
        echo "  check             Check development environment"
        echo "  clean [path]      Clean Flutter project (default: current directory)"
        echo "  build [path]      Build APK for Flutter project (default: current directory)"
        echo "  test [path]       Run tests for Flutter project (default: current directory)"
        echo ""
        echo "Examples:"
        echo "  $0 create my_awesome_app"
        echo "  $0 emulator"
        echo "  $0 check"
        echo "  $0 clean ./my_app"
        echo "  $0 build ./my_app"
        echo "  $0 test ./my_app"
        ;;
esac