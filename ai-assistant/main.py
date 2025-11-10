#!/usr/bin/env python3
"""
AI Assistant Service Entry Point
This is the main entry point for running the AI Assistant service.
"""
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Run the application
from ai_assistant.__main__ import main
import asyncio

if __name__ == '__main__':
    asyncio.run(main())
