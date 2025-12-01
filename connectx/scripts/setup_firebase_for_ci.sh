#!/bin/bash
# Script to ensure Firebase configuration files exist for CI/testing
# Copies stub files if the real Firebase configuration files don't exist

FIREBASE_OPTIONS="lib/firebase_options.dart"
FIREBASE_STUB="lib/firebase_options_stub.dart"
GOOGLE_SERVICES_ANDROID="android/app/google-services.json"
GOOGLE_SERVICES_ANDROID_STUB="android/app/google-services.json.stub"
GOOGLE_SERVICES_IOS="ios/Runner/GoogleService-Info.plist"
GOOGLE_SERVICES_IOS_STUB="ios/Runner/GoogleService-Info.plist.stub"

# Setup firebase_options.dart for Flutter
if [ ! -f "$FIREBASE_OPTIONS" ]; then
    echo "firebase_options.dart not found. Using stub file for testing..."
    cp "$FIREBASE_STUB" "$FIREBASE_OPTIONS"
    echo "✓ Created $FIREBASE_OPTIONS from stub"
else
    echo "✓ firebase_options.dart already exists"
fi

# Setup google-services.json for Android build
if [ ! -f "$GOOGLE_SERVICES_ANDROID" ]; then
    echo "google-services.json not found. Using stub file for CI build..."
    cp "$GOOGLE_SERVICES_ANDROID_STUB" "$GOOGLE_SERVICES_ANDROID"
    echo "✓ Created $GOOGLE_SERVICES_ANDROID from stub"
else
    echo "✓ google-services.json already exists"
fi

# Setup GoogleService-Info.plist for iOS build
if [ ! -f "$GOOGLE_SERVICES_IOS" ]; then
    echo "GoogleService-Info.plist not found. Using stub file for CI build..."
    cp "$GOOGLE_SERVICES_IOS_STUB" "$GOOGLE_SERVICES_IOS"
    echo "✓ Created $GOOGLE_SERVICES_IOS from stub"
else
    echo "✓ GoogleService-Info.plist already exists"
fi

echo ""
echo "Firebase configuration setup complete for CI/testing"


