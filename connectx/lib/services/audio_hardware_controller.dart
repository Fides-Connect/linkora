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
    // Input device selection is handled at the getUserMedia level in WebRTC.
    // Here we make a best-effort attempt to obtain a stream from the requested
    // input device so callers can rely on this method to actually try to route
    // audio to the specified microphone.
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
