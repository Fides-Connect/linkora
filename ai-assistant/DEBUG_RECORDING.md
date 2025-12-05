# Server-Side Debug Audio Recording

## Overview
The AI-Assistant server can record all audio received from clients for debugging purposes. This helps diagnose audio quality issues, transmission problems, and STT failures.

## Configuration

### Enable Recording
In `ai-assistant/.env`:
```env
DEBUG_RECORD_AUDIO=true
```

Set to `false` or remove to disable.

### Output Location
Recordings are saved to:
```
ai-assistant/debug_audio/received_audio_<connection_id>_<timestamp>.wav
```

Example: `received_audio_4633586592_20251204_131351.wav`

## Audio Format
- **Sample rate**: 48kHz
- **Bit depth**: 16-bit PCM
- **Channels**: Mono (1 channel)
- **Format**: WAV

## How It Works

The server captures audio frames received from WebRTC and saves them to WAV files:

1. Client connects and starts sending audio via WebRTC
2. Server receives audio frames (20ms chunks at 48kHz = 960 samples)
3. If `DEBUG_RECORD_AUDIO=true`, frames are buffered in memory
4. When connection ends, all frames are concatenated and saved as WAV

## Usage

### Check Recording Status
Look for these log messages when server starts:
```
INFO - Debug Audio Record: true
```

When a client connects:
```
INFO - Debug audio recording enabled: debug_audio/received_audio_4633586592_20251204_131351.wav
```

When connection ends:
```
INFO - Saving debug recording: debug_audio/received_audio_4633586592_20251204_131351.wav
INFO - Recording 1020 frames, lengths: min=960, max=960, avg=960.0
INFO - Audio stats: min=-32768, max=32767, RMS=23049.43
INFO - Debug recording saved: debug_audio/received_audio_4633586592_20251204_131351.wav (20.40s, 979200 samples)
```

### Analyze Recordings

#### Play Audio
```bash
# macOS
afplay debug_audio/received_audio_*.wav

# Linux
aplay debug_audio/received_audio_*.wav

# VLC (cross-platform)
vlc debug_audio/received_audio_*.wav
```

#### Check Audio Properties
```bash
# Using ffprobe
ffprobe debug_audio/received_audio_4633586592_20251204_131351.wav

# Using soxi (SoX)
soxi debug_audio/received_audio_4633586592_20251204_131351.wav
```

#### Analyze with Audacity
1. Open Audacity
2. File → Open → Select WAV file
3. View waveform, check for:
   - Clipping (audio peaks at ±32767)
   - Low volume (RMS < 1000)
   - Silence (flat line)
   - Noise (high frequency content)

## Troubleshooting

### No Recording Created
- Check `DEBUG_RECORD_AUDIO=true` in `.env`
- Verify `debug_audio/` directory exists (auto-created)
- Ensure connection completed successfully
- Check server logs for errors

### Recording is Silent
- Check Flutter app microphone permissions
- Verify WebRTC connection established
- Look for "Frame receive cancelled" in logs (indicates connection lost)
- Check RMS values in logs - should be > 1000 for speech

### Recording is Distorted/Clipped
- Check RMS values in logs
- RMS > 30000 indicates clipping
- Review microphone gain settings on device
- Check WebRTC audio processing constraints

## Performance Impact

- **Memory**: ~1.9 KB per frame (20ms), ~95 KB per second
- **CPU**: Minimal (just memory copy)
- **Disk I/O**: Only on connection close
- **Typical file size**: ~5.5 MB per minute at 48kHz mono

Disable in production if not needed to save disk space.

## Example Log Analysis

### Successful Recording
```
[Frame 50] Queued 1920 bytes (RMS=22984.96)   ← Good signal level
[Frame 100] Queued 1920 bytes (RMS=23474.56)  ← Consistent RMS
...
Debug recording saved: ... (20.40s, 979200 samples)  ← Full session recorded
```

### Silent Audio
```
[Frame 50] Queued 1920 bytes (RMS=23.45)      ← Very low RMS
[Frame 100] Queued 1920 bytes (RMS=18.92)     ← Background noise only
```

### Connection Lost
```
[Frame 50] Queued 1920 bytes (RMS=22984.96)
Frame receive cancelled (frame 51)             ← Connection dropped
```

## Comparison with STT Issues

If you see frames being received but no STT transcripts:
1. Check RMS values - speech should be > 1000
2. Play the recorded WAV - verify it contains actual speech
3. If recording has speech but STT fails:
   - Issue is with Google STT (language, model, format)
4. If recording is silent/noise:
   - Issue is with client audio capture or WebRTC transmission

## Current Status

✅ **Server-side recording is ENABLED and WORKING**

Your logs show:
- `DEBUG_RECORD_AUDIO=true` in environment
- Recording successfully saved: 20.4s, 979200 samples
- RMS ~23000 (good speech level)
- All 1020 frames captured successfully

The recording feature is fully functional!
