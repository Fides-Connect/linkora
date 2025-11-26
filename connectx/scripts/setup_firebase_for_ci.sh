#!/bin/bash
# Script to ensure firebase_options.dart exists for CI/testing
# Copies stub file if the real firebase_options.dart doesn't exist

FIREBASE_OPTIONS="lib/firebase_options.dart"
FIREBASE_STUB="lib/firebase_options_stub.dart"

if [ ! -f "$FIREBASE_OPTIONS" ]; then
    echo "firebase_options.dart not found. Using stub file for testing..."
    cp "$FIREBASE_STUB" "$FIREBASE_OPTIONS"
    echo "Created $FIREBASE_OPTIONS from stub"
else
    echo "firebase_options.dart already exists"
fi
