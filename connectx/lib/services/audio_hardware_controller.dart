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
    // Note: Input device selection is handled at getUserMedia level in WebRTC
    // This is a placeholder for potential future implementation
    // For now, the default microphone will switch when Bluetooth connects
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
