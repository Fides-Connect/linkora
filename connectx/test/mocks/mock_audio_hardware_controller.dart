import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:connectx/services/audio_hardware_controller.dart';

/// Mock implementation of AudioHardwareController for testing
class MockAudioHardwareController implements AudioHardwareController {
  bool _speakerphoneOn = false;
  List<MediaDeviceInfo> _audioDevices = [];
  Function(dynamic)? _onDeviceChange;
  final List<String> _enumerateTypes = [];
  String? _selectedAudioOutputId;
  String? _selectedAudioInputId;

  /// Track state for verification
  bool get speakerphoneOn => _speakerphoneOn;
  List<MediaDeviceInfo> get audioDevices => _audioDevices;
  List<String> get enumerateTypes => List.unmodifiable(_enumerateTypes);
  String? get selectedAudioOutputId => _selectedAudioOutputId;
  String? get selectedAudioInputId => _selectedAudioInputId;

  /// Simulate Bluetooth device connection/disconnection
  void setBluetoothConnected(bool connected) {
    if (connected) {
      _audioDevices = [
        MediaDeviceInfo(
          deviceId: 'bluetooth-1',
          label: 'Bluetooth Headset',
          kind: 'audioinput',
          groupId: 'group-1',
        ),
        MediaDeviceInfo(
          deviceId: 'bluetooth-2',
          label: 'Bluetooth Headset',
          kind: 'audiooutput',
          groupId: 'group-1',
        ),
      ];
    } else {
      _audioDevices = [];
    }
    // Don't trigger device change callback in tests - let the test control when routing happens
    // This prevents race conditions between the callback and explicit test calls
    // _onDeviceChange?.call(null);
  }

  @override
  Future<void> setSpeakerphoneOn(bool enable) async {
    _speakerphoneOn = enable;
  }

  @override
  Future<List<MediaDeviceInfo>> enumerateDevices(String type) async {
    _enumerateTypes.add(type);
    return _audioDevices.where((device) => device.kind == type).toList();
  }

  @override
  Future<void> selectAudioOutput(String deviceId) async {
    _selectedAudioOutputId = deviceId;
  }

  @override
  Future<void> selectAudioInput(String deviceId) async {
    _selectedAudioInputId = deviceId;
  }

  @override
  set onDeviceChange(Function(dynamic)? callback) {
    _onDeviceChange = callback;
  }
}
