#!/usr/bin/env python3
"""
AI Assistant Service Entry Point
This is the main entry point for running the AI Assistant service.
"""

# Run the application
from ai_assistant.__main__ import main
import asyncio

if __name__ == '__main__':
    asyncio.run(main())
