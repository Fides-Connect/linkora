#!/bin/bash
# Script to ensure firebase_options.dart and google-services.json exist for CI/testing
# Copies stub files if the real files don't exist

FIREBASE_OPTIONS="lib/firebase_options.dart"
FIREBASE_STUB="lib/firebase_options_stub.dart"
GOOGLE_SERVICES_JSON="android/app/google-services.json"
GOOGLE_SERVICES_TEMPLATE="android/app/google-services.json.template"

# Setup firebase_options.dart
if [ ! -f "$FIREBASE_OPTIONS" ]; then
    echo "firebase_options.dart not found. Using stub file for testing..."
    cp "$FIREBASE_STUB" "$FIREBASE_OPTIONS"
    echo "Created $FIREBASE_OPTIONS from stub"
else
    echo "firebase_options.dart already exists"
fi

# Setup google-services.json from environment variable or template
if [ ! -f "$GOOGLE_SERVICES_JSON" ]; then
    if [ -n "$GOOGLE_SERVICES_JSON_CONTENT" ]; then
        echo "Creating google-services.json from environment variable..."
        echo "$GOOGLE_SERVICES_JSON_CONTENT" > "$GOOGLE_SERVICES_JSON"
        echo "Created $GOOGLE_SERVICES_JSON from secret"
    elif [ -f "$GOOGLE_SERVICES_TEMPLATE" ]; then
        echo "Creating google-services.json from template..."
        cp "$GOOGLE_SERVICES_TEMPLATE" "$GOOGLE_SERVICES_JSON"
        echo "Created $GOOGLE_SERVICES_JSON from template (placeholder values)"
    else
        echo "ERROR: Neither GOOGLE_SERVICES_JSON_CONTENT env var nor template file found"
        exit 1
    fi
else
    echo "google-services.json already exists"
fi
