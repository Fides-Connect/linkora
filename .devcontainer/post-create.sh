#!/bin/bash

# Create Python Virtual Environment and install dependencies
echo "🐍 Installing Python dependencies..."
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e "./ai-assistant[dev]"
echo "source /workspaces/Linkora/.venv/bin/activate" >> ~/.bashrc

# Run Flutter doctor to check setup
echo "🔍 Running Flutter doctor..."
/opt/flutter/bin/flutter doctor -v