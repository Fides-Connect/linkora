import 'package:flutter/foundation.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

/// Abstract interface for audio hardware control
/// Allows mocking in tests while using real implementation in production
abstract class AudioHardwareController {
  /// Set speakerphone on/off
  Future<void> setSpeakerphoneOn(bool enabled);
  
  /// Enumerate available audio devices
  Future<List<MediaDeviceInfo>> enumerateDevices(String type);
  
  /// Select specific audio output device
  Future<void> selectAudioOutput(String deviceId);
  
  /// Select specific audio input device
  Future<void> selectAudioInput(String deviceId);
  
  /// Set callback for device changes
  set onDeviceChange(Function(dynamic)? callback);
}

/// Production implementation using flutter_webrtc Helper
class FlutterWebRTCAudioController implements AudioHardwareController {
  @override
  Future<void> setSpeakerphoneOn(bool enabled) async {
    await Helper.setSpeakerphoneOn(enabled);
  }
  
  @override
  Future<List<MediaDeviceInfo>> enumerateDevices(String type) async {
    return await Helper.enumerateDevices(type);
  }

  @override
  Future<void> selectAudioOutput(String deviceId) async {
    await Helper.selectAudioOutput(deviceId);
  }
  
  @override
  Future<void> selectAudioInput(String deviceId) async {
    // WebRTC input device selection is handled at getUserMedia level - there's no direct
    // API to switch input devices on an existing stream. This method creates a temporary
    // stream to verify the device can be accessed and signal intent to the platform.
    // 
    // Tradeoffs:
    // - May trigger permission prompts on first call (mitigated by prior mic permissions)
    // - Creates/disposes a stream (acceptable - only called during device changes, not frequently)
    // - Platform audio routing may happen automatically when device connects (this validates it)
    //
    // This approach is necessary because:
    // 1. No browser API exists to select input device without creating a stream
    // 2. The actual input switch happens at stream creation time (WebRTCService recreates stream)
    // 3. This validates the device is accessible before the full stream recreation
    try {
      final mediaConstraints = {
        'audio': <String, dynamic>{
          'deviceId': deviceId,
        },
        'video': false,
      };

      final MediaStream stream =
          await navigator.mediaDevices.getUserMedia(mediaConstraints);

      // We don't need to keep the stream here; stop and dispose tracks
      // immediately after verifying that the device can be opened.
      for (var track in stream.getTracks()) {
        track.stop();
      }
      await stream.dispose();
    } catch (e) {
      // Preserve previous behavior: do not throw if input selection is
      // not supported or fails. Callers can still rely on automatic
      // platform routing (e.g., when Bluetooth connects).
      if (kDebugMode) {
        debugPrint('AudioHardwareController: Failed to select input device $deviceId: $e');
      }
    }
  }
  
  @override
  set onDeviceChange(Function(dynamic)? callback) {
    try {
      navigator.mediaDevices.ondevicechange = callback;
    } catch (e) {
      // Ignore if not supported
    }
  }
}
