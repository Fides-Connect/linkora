#!/bin/bash

# Create Python Virtual Environment and install dependencies
echo "🐍 Installing Python dependencies..."
python -m venv .venv
python -m pip install --upgrade pip
.venv/bin/pip install -r ./ai-assistant/requirements.txt
.venv/bin/pip install -r ./connectx/requirements.txt
echo "source /workspaces/Fides/.venv/bin/activate" >> ~/.bashrc

# Run Flutter doctor to check setup
echo "🔍 Running Flutter doctor..."
/opt/flutter/bin/flutter doctor -v