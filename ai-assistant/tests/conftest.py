"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
import socket
from unittest.mock import Mock, patch


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


@pytest.fixture(scope="session", autouse=True)
def mock_weaviate_connection(weaviate_available):
    """Mock Weaviate connections only when Weaviate is not available (e.g., in CI).
    
    This fixture automatically applies to all tests. When Weaviate is running locally,
    it does nothing and allows real connections. When Weaviate is unavailable (CI),
    it mocks the connection to prevent test failures.
    """
    if weaviate_available:
        # Weaviate is running, don't mock - allow real connections
        yield None
    else:
        # Weaviate is not available, use mocks
        mock_client = Mock()
        mock_client.is_ready.return_value = True
        mock_client.collections = Mock()
        
        # Patch the HubSpokeConnection to return our mock client
        with patch('ai_assistant.hub_spoke_schema.HubSpokeConnection.get_client', return_value=mock_client), \
             patch('ai_assistant.hub_spoke_schema.weaviate.connect_to_custom', return_value=mock_client), \
             patch('ai_assistant.hub_spoke_schema.weaviate.connect_to_wcs', return_value=mock_client):
            yield mock_client


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables before each test."""
    # Set safe defaults for testing
    monkeypatch.setenv('GEMINI_API_KEY', 'test-api-key')
    monkeypatch.setenv('LANGUAGE_CODE', 'de-DE')
    monkeypatch.setenv('VOICE_NAME', 'de-DE-Test-Voice')
    monkeypatch.setenv('DEBUG_RECORD_AUDIO', 'false')
    monkeypatch.setenv('GOOGLE_TTS_API_CONCURRENCY', '5')
