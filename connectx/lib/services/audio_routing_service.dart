import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:permission_handler/permission_handler.dart';
import 'audio_hardware_controller.dart';

/// Service to manage audio routing for WebRTC calls
/// Handles switching between loudspeaker and Bluetooth headsets
class AudioRoutingService {
  bool _isSpeakerOn = true;
  bool _isBluetoothSpeakerConnected = false;
  bool _isBluetoothMicrophoneConnected = false;
  bool _isCheckingDevices = false;
  Timer? _deviceCheckTimer;
  Timer? _inputDeviceChangeDebounce;
  final AudioHardwareController _hardwareController;
  
  // Configurable durations for testing
  final Duration deviceCheckInterval;
  final Duration inputChangeDebounce;
  final Duration bluetoothSetupDelay;

  /// Callback when audio routing changes
  Function(AudioRouting)? onAudioRoutingChanged;
  
  /// Callback when input device changes and may require track recreation
  /// This is important for mid-stream device switching (e.g., Bluetooth connects during call)
  Future<void> Function()? onInputDeviceChanged;

  AudioRoutingService({
    AudioHardwareController? hardwareController,
    this.deviceCheckInterval = const Duration(seconds: 3),
    this.inputChangeDebounce = const Duration(milliseconds: 10),
    this.bluetoothSetupDelay = const Duration(milliseconds: 500),
  }) : _hardwareController = hardwareController ?? FlutterWebRTCAudioController();

  /// Initialize audio routing with auto-detection
  Future<void> initialize() async {
    if (kIsWeb) return;

    try {
      await _requestPermissions();
      await checkAndRouteAudio(forceUpdate: true);
      _startAudioDeviceMonitoring();
    } on MissingPluginException {
      // In test environments, plugins may not be available - continue without permissions
      await checkAndRouteAudio(forceUpdate: true);
      _startAudioDeviceMonitoring();
    } catch (e) {
      debugPrint('AudioRouting: Initialization error: $e');
      rethrow;
    }
  }

  /// Request necessary permissions for audio routing
  Future<void> _requestPermissions() async {
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      try {
        final permissions = [
          Permission.microphone,
          Permission.bluetoothConnect,
          Permission.bluetoothScan,
        ];
        
        await permissions.request();
      } on MissingPluginException {
        // In test environments, permission_handler plugin is not available
        // This is expected and not an error - tests use mocks
      }
    }
  }

  /// Start monitoring audio device changes
  void _startAudioDeviceMonitoring() {
    _hardwareController.onDeviceChange = (dynamic event) {
      unawaited(
        checkAndRouteAudio().catchError((error) {
          debugPrint('AudioRouting: Error in device change handler: $error');
        }),
      );
    };

    _deviceCheckTimer = Timer.periodic(deviceCheckInterval, (timer) {
      unawaited(
        checkAndRouteAudio().catchError((error) {
          debugPrint('AudioRouting: Error in periodic check: $error');
        }),
      );
    });
  }

  /// Notify callback about input device change with debouncing
  void _notifyInputDeviceChanged() {
    if (onInputDeviceChanged == null) return;
    
    // Cancel any pending notification
    _inputDeviceChangeDebounce?.cancel();
    
    // Schedule debounced notification
    _inputDeviceChangeDebounce = Timer(inputChangeDebounce, () {
      unawaited(
        onInputDeviceChanged!().catchError((error) {
          debugPrint('AudioRouting: Error recreating track on input change: $error');
        }),
      );
    });
  }

  /// Check available audio devices and route audio immediately
  /// Can be called manually at any time to re-evaluate routing
  /// 
  /// Priority:
  /// 1. Bluetooth Headset Speaker (output) + Bluetooth Microphone (input)
  /// 2. Loudspeaker (output) + Phone Microphone (input) - Default
  /// 3. Earpiece (Manual only)
  Future<void> checkAndRouteAudio({bool forceUpdate = false}) async {
    // Prevent overlapping executions
    if (_isCheckingDevices) {
      return;
    }
    
    _isCheckingDevices = true;
    try {
      // Check available audio output devices
      var outputDevices = await _hardwareController.enumerateDevices('audiooutput');
      var inputDevices = await _hardwareController.enumerateDevices('audioinput');
      
      // Look for Bluetooth devices or headsets in both input and output
      // Each list is searched independently - never mix input/output device types
      MediaDeviceInfo? bluetoothOutputDevice;
      MediaDeviceInfo? bluetoothInputDevice;
      
      // Check output devices for Bluetooth speaker
      for (final device in outputDevices) {
        final label = device.label.toLowerCase();
        final id = device.deviceId.toLowerCase();

        final isBluetooth = label.contains('bluetooth') ||
            label.contains('headset') ||
            label.contains('airpods') ||
            label.contains('earbuds') ||
            label.contains('bt') ||
            id.contains('bluetooth');

        if (isBluetooth) {
          bluetoothOutputDevice = device;
          break;
        }
      }
      
      // Check input devices for Bluetooth microphone
      for (final device in inputDevices) {
        final label = device.label.toLowerCase();
        final id = device.deviceId.toLowerCase();

        final isBluetooth = label.contains('bluetooth') ||
            label.contains('headset') ||
            label.contains('airpods') ||
            label.contains('earbuds') ||
            label.contains('bt') ||
            id.contains('bluetooth');

        if (isBluetooth) {
          bluetoothInputDevice = device;
          break;
        }
      }

      final hasBluetoothSpeaker = bluetoothOutputDevice != null;
      final hasBluetoothMic = bluetoothInputDevice != null;

      if (hasBluetoothSpeaker && hasBluetoothMic) {
        // Bluetooth devices found (both speaker and mic) - require BOTH speaker (output) and mic (input)
        // to ensure full-duplex Bluetooth audio communication. Having only one prevents
        // proper bidirectional audio (e.g., only Bluetooth mic would route output to loudspeaker).
        // Check if input device status changed
        final inputDeviceChanged = hasBluetoothMic != _isBluetoothMicrophoneConnected;
        
        // Switch if we are not already connected OR if we are forcing an update
        if (!_isBluetoothSpeakerConnected || !_isBluetoothMicrophoneConnected || forceUpdate) {
          await _setBluetoothAudio(
            outputDeviceId: bluetoothOutputDevice?.deviceId,
            inputDeviceId: bluetoothInputDevice?.deviceId,
          );
          
          // Notify if input device changed (may need to recreate audio track)
          if (inputDeviceChanged) {
            _notifyInputDeviceChanged();
          }
        }
      } else {
        // No Bluetooth device - Default to Loudspeaker + Phone Mic
        // Check if input device status changed
        final inputDeviceChanged = _isBluetoothMicrophoneConnected;
        
        // Only switch if we were previously on Bluetooth OR if forcing update
        if (_isBluetoothSpeakerConnected || _isBluetoothMicrophoneConnected || forceUpdate) {
          // If we were on Bluetooth and it disconnected, fall back to Loudspeaker
          // Or if this is initialization (forceUpdate), default to Loudspeaker
          try {
            await _setLoudspeaker();
            
            // Notify if input device changed (may need to recreate audio track)
            if (inputDeviceChanged) {
              _notifyInputDeviceChanged();
            }
          } catch (_) {
            // If loudspeaker routing fails, fall back to earpiece
            await setEarpiece();
          }
        }
      }
    } catch (e) {
      debugPrint('AudioRouting: Error handling audio device change: $e');
    } finally {
      _isCheckingDevices = false;
    }
  }

  /// Set audio routing to loudspeaker (output) and phone microphone (input)
  Future<void> _setLoudspeaker() async {
    try {
      await _hardwareController.setSpeakerphoneOn(true);
      _isSpeakerOn = true;
      _isBluetoothSpeakerConnected = false;
      _isBluetoothMicrophoneConnected = false;
      onAudioRoutingChanged?.call(AudioRouting.loudspeaker);
    } catch (e) {
      debugPrint('AudioRouting: Loudspeaker error: $e');
      rethrow;
    }
  }

  /// Set audio routing to Bluetooth speaker (output) and/or Bluetooth microphone (input)
  Future<void> _setBluetoothAudio({
    String? outputDeviceId,
    String? inputDeviceId,
  }) async {
    try {
      // Select output device if provided
      if (outputDeviceId != null) {
        await _hardwareController.selectAudioOutput(outputDeviceId);
      }
      
      // Select input device if provided
      if (inputDeviceId != null) {
        await _hardwareController.selectAudioInput(inputDeviceId);
      }

      await _hardwareController.setSpeakerphoneOn(true);
      if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
        await Helper.setAndroidAudioConfiguration(AndroidAudioConfiguration(
          androidAudioMode: AndroidAudioMode.inCommunication,
          androidAudioStreamType: AndroidAudioStreamType.voiceCall,
          androidAudioAttributesUsageType: AndroidAudioAttributesUsageType.voiceCommunication,
        ));
      }
      // Android requires speakerphone to be toggled on then off to route Bluetooth audio correctly
      // This delay allows the audio system to stabilize before disabling speakerphone
      await Future.delayed(bluetoothSetupDelay);
      await _hardwareController.setSpeakerphoneOn(false);
      
      // Only update state flags after all operations complete successfully
      _isBluetoothSpeakerConnected = outputDeviceId != null;
      _isBluetoothMicrophoneConnected = inputDeviceId != null;
      _isSpeakerOn = false;
      onAudioRoutingChanged?.call(AudioRouting.bluetooth);
    } catch (e) {
      debugPrint('AudioRouting: Bluetooth setup error: $e');
      // Routing failed - clear Bluetooth state and fall back to loudspeaker
      _isBluetoothSpeakerConnected = false;
      _isBluetoothMicrophoneConnected = false;
      try {
        await _setLoudspeaker();
      } catch (fallbackError) {
        debugPrint('AudioRouting: Fallback to loudspeaker failed: $fallbackError');
      }
      rethrow;
    }
  }

  /// Manually set audio routing to loudspeaker
  Future<void> setLoudspeaker() async {
    await _setLoudspeaker();
  }

  /// Manually set audio routing to earpiece (for phone call style)
  Future<void> setEarpiece() async {
    try {
      await _hardwareController.setSpeakerphoneOn(false);
      _isSpeakerOn = false;
      _isBluetoothSpeakerConnected = false;
      _isBluetoothMicrophoneConnected = false;
      onAudioRoutingChanged?.call(AudioRouting.earpiece);
    } catch (e) {
      debugPrint('AudioRouting: Error setting earpiece: $e');
      rethrow;
    }
  }

  /// Get current audio routing state
  AudioRouting getCurrentRouting() {
    if (_isBluetoothSpeakerConnected || _isBluetoothMicrophoneConnected) {
      return AudioRouting.bluetooth;
    } else if (_isSpeakerOn) {
      return AudioRouting.loudspeaker;
    } else {
      return AudioRouting.earpiece;
    }
  }

  /// Check if Bluetooth speaker is currently connected
  bool get isBluetoothSpeakerConnected => _isBluetoothSpeakerConnected;
  
  /// Check if Bluetooth microphone is currently connected
  bool get isBluetoothMicrophoneConnected => _isBluetoothMicrophoneConnected;
  
  /// Check if any Bluetooth audio device is connected
  bool get isBluetoothConnected => _isBluetoothSpeakerConnected || _isBluetoothMicrophoneConnected;

  /// Check if loudspeaker is currently active
  bool get isSpeakerOn => _isSpeakerOn;

  /// Dispose and clean up resources
  void dispose() {
    _deviceCheckTimer?.cancel();
    _deviceCheckTimer = null;
    _inputDeviceChangeDebounce?.cancel();
    _inputDeviceChangeDebounce = null;
    _hardwareController.onDeviceChange = null;
  }
}

/// Audio routing options
enum AudioRouting {
  loudspeaker,
  earpiece,
  bluetooth,
}
