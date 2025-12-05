"""
Pytest configuration and shared fixtures.
"""
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables before each test."""
    # Set safe defaults for testing
    monkeypatch.setenv('GEMINI_API_KEY', 'test-api-key')
    monkeypatch.setenv('LANGUAGE_CODE', 'de-DE')
    monkeypatch.setenv('VOICE_NAME', 'de-DE-Test-Voice')
    monkeypatch.setenv('USE_WEAVIATE', 'false')
    monkeypatch.setenv('DEBUG_RECORD_AUDIO', 'false')
    monkeypatch.setenv('GOOGLE_TTS_API_CONCURRENCY', '5')
