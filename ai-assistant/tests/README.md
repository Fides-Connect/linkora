# Tests

This directory contains test files and validation scripts for the AI Assistant.

## Files

- `test_client.py` - WebRTC test client for end-to-end testing
- `validate.py` - Configuration and setup validator
- `__init__.py` - Test package marker

## Running Tests

### Validate Setup

Check if your configuration is correct before running the service:

```bash
# From project root
python tests/validate.py

# Or from tests directory
cd tests
python validate.py
```

This checks:
- Environment file (`.env`)
- Google Cloud credentials
- Required dependencies
- Port availability
- Network connectivity
- File structure

### Test WebRTC Connection

Test the WebRTC connection with a sample audio file:

```bash
# From project root
python tests/test_client.py --audio-file path/to/audio.wav

# With custom server URL
python tests/test_client.py --server ws://192.168.1.100:8080/ws --audio-file test.wav

# Specify test duration
python tests/test_client.py --audio-file test.wav --duration 60
```

#### Audio File Requirements

The test client requires a WAV file with:
- **Sample Rate**: 16000 Hz (16 kHz)
- **Channels**: 1 (mono)
- **Sample Width**: 16-bit (2 bytes)
- **Format**: PCM

Convert audio to the correct format:

```bash
# Using ffmpeg
ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 output.wav

# Using sox
sox input.mp3 -r 16000 -c 1 -b 16 output.wav
```

## Test Workflow

1. **Validate Configuration**
   ```bash
   python tests/validate.py
   ```

2. **Start the Service**
   ```bash
   # Local
   python main.py
   
   # Or container
   ./run.sh start
   ```

3. **Run Test Client**
   ```bash
   python tests/test_client.py --audio-file test.wav
   ```

4. **Check Output**
   - Test client will connect via WebRTC
   - Send audio from the WAV file
   - Receive and save response to `output.wav`

## Writing New Tests

### Unit Tests

Place unit tests in this directory with `test_` prefix:

```python
# test_audio_processor.py
import unittest
from ai_assistant.audio_processor import AudioProcessor

class TestAudioProcessor(unittest.TestCase):
    def test_silence_detection(self):
        # Your test here
        pass
```

Run with:
```bash
python -m unittest discover tests/
```

### Integration Tests

For integration tests, use the test client as a template:

```python
# test_integration.py
from test_client import TestClient
import asyncio

async def test_full_pipeline():
    client = TestClient()
    await client.run("test_audio.wav", duration=10)
```

## Troubleshooting

### Import Errors

If you get import errors when running tests:

```bash
# Install package in development mode
pip install -e .
```

### Connection Errors

If test client can't connect:

1. Check service is running: `curl http://localhost:8080/health`
2. Verify WebSocket URL is correct
3. Check firewall settings
4. Review service logs: `./run.sh logs`

### Audio Issues

If audio test fails:

1. Verify audio file format (16kHz, mono, 16-bit)
2. Check Google Cloud credentials
3. Ensure APIs are enabled
4. Review service logs for errors

## Continuous Integration

For CI/CD pipelines:

```yaml
# .github/workflows/test.yml (example)
- name: Validate Setup
  run: python tests/validate.py

- name: Run Unit Tests
  run: python -m unittest discover tests/

- name: Test Container Build
  run: ./run.sh build
```

## Future Tests

Consider adding:
- Unit tests for each module
- Integration tests for full pipeline
- Load testing for concurrent connections
- Audio quality tests
- Latency benchmarks
- Error handling tests
- Mock tests for Google Cloud APIs
