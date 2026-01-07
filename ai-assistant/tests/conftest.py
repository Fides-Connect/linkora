"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
import socket


def is_weaviate_available(host='localhost', port=8090, timeout=1):
    """Check if Weaviate is running and accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def weaviate_available():
    """Check if Weaviate is available for integration tests."""
    return is_weaviate_available()


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
