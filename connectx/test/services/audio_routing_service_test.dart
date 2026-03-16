import 'package:flutter_test/flutter_test.dart';
import 'package:connectx/services/audio_routing_service.dart';
import '../mocks/mock_audio_hardware_controller.dart';
import '../helpers/test_constants.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  _aecConfigTests();

  group('AudioRoutingService - Initialization', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(
        hardwareController: mockController,
        bluetoothSetupDelay: testBluetoothSetupDelay,
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('initializes with loudspeaker as default', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);
      expect(service.isSpeakerOn, true);
      expect(service.isBluetoothConnected, false);
    });

    test('hardware controller receives setSpeakerphoneOn(true) on init', () async {
      await service.initialize();
      expect(mockController.speakerphoneOn, true);
    });

    test('initializes with Bluetooth when available', () async {
      mockController.setBluetoothConnected(true);
      await service.initialize();

      expect(service.getCurrentRouting(), AudioRouting.bluetooth);
      expect(service.isBluetoothConnected, true);
      expect(service.isSpeakerOn, false);
    });

    test('enumerates audiooutput devices first', () async {
      await service.initialize();

      expect(mockController.enumerateTypes.contains('audiooutput'), true);
    });
  });

  group('AudioRoutingService - Bluetooth Auto-Detection', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(
        hardwareController: mockController,
        deviceCheckInterval: testDeviceCheckInterval,
        inputChangeDebounce: testInputChangeDebounce,
        bluetoothSetupDelay: testBluetoothSetupDelay,
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('detects Bluetooth device connection', () async {
      await service.initialize();
      expect(service.isBluetoothConnected, false);

      mockController.setBluetoothConnected(true);
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(service.isBluetoothConnected, true);
    });

    test('selects Bluetooth audio output device when available', () async {
      await service.initialize();

      mockController.setBluetoothConnected(true);
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(mockController.selectedAudioOutputId, 'bluetooth-2');
    });

    test('routing automatically switches from loudspeaker to Bluetooth', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      mockController.setBluetoothConnected(true);
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(service.getCurrentRouting(), AudioRouting.bluetooth);
    });

    test('hardware controller switches speakerphone OFF when Bluetooth connects', () async {
      await service.initialize();
      expect(mockController.speakerphoneOn, true);

      mockController.setBluetoothConnected(true);
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(mockController.speakerphoneOn, false);
    });
  });

  group('AudioRoutingService - Manual Routing Control', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(
        hardwareController: mockController,
        deviceCheckInterval: testDeviceCheckInterval,
        inputChangeDebounce: testInputChangeDebounce,
        bluetoothSetupDelay: testBluetoothSetupDelay,
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('user can manually switch to earpiece', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      await service.setEarpiece();

      expect(service.getCurrentRouting(), AudioRouting.earpiece);
    });

    test('user can manually switch to loudspeaker', () async {
      await service.initialize();
      await service.setEarpiece();
      expect(service.getCurrentRouting(), AudioRouting.earpiece);

      await service.setLoudspeaker();

      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);
    });
  });

  group('AudioRoutingService - State Tracking', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(
        hardwareController: mockController,
        deviceCheckInterval: testDeviceCheckInterval,
        inputChangeDebounce: testInputChangeDebounce,
        bluetoothSetupDelay: testBluetoothSetupDelay,
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('isSpeakerOn property accurately reflects current state', () async {
      await service.initialize();
      expect(service.isSpeakerOn, true);

      await service.setEarpiece();
      expect(service.isSpeakerOn, false);

      await service.setLoudspeaker();
      expect(service.isSpeakerOn, true);
    });

    test('isBluetoothConnected property accurately reflects Bluetooth status', () async {
      await service.initialize();
      expect(service.isBluetoothConnected, false);

      mockController.setBluetoothConnected(true);
      await service.checkAndRouteAudio(forceUpdate: true);
      expect(service.isBluetoothConnected, true);

      mockController.setBluetoothConnected(false);
      await service.checkAndRouteAudio(forceUpdate: true);
      expect(service.isBluetoothConnected, false);
    });

    test('getCurrentRouting returns correct AudioRouting enum value', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      await service.setEarpiece();
      expect(service.getCurrentRouting(), AudioRouting.earpiece);

      await service.setLoudspeaker();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      mockController.setBluetoothConnected(true);
      await service.checkAndRouteAudio(forceUpdate: true);
      expect(service.getCurrentRouting(), AudioRouting.bluetooth);
    });
  });
}
// ════════════════════════════════════════════════════════════════════════════
// Android AEC configuration tests
// ════════════════════════════════════════════════════════════════════════════
// These tests verify that setAndroidAudioConfig() is called whenever audio
// routing is established in loudspeaker or Bluetooth mode, which is required
// for Android hardware AEC (acoustic echo cancellation) to engage.  Without
// MODE_IN_COMMUNICATION the OS uses MODE_NORMAL (media playback) and hardware
// AEC is disabled, causing STT to transcribe TTS output as user speech.
// ════════════════════════════════════════════════════════════════════════════

// NOTE: These tests run outside of the existing main() because they need their
// own group scope. Dart test runners collect all top-level groups. See the
// second main() call below — Flutter test supports multiple top-level groups
// defined in separate helper functions called from a single main().
void _aecConfigTests() {
  group('AudioRoutingService - Android AEC Configuration', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(
        hardwareController: mockController,
        deviceCheckInterval: testDeviceCheckInterval,
        inputChangeDebounce: testInputChangeDebounce,
        bluetoothSetupDelay: testBluetoothSetupDelay,
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('setAndroidAudioConfig is called during loudspeaker init', () async {
      await service.initialize();
      // initialize() → checkAndRouteAudio(forceUpdate:true) → _setLoudspeaker()
      expect(
        mockController.androidAudioConfigCallCount,
        greaterThanOrEqualTo(1),
        reason: 'Android AEC must be configured for loudspeaker mode',
      );
    });

    test('setAndroidAudioConfig is called when switching to loudspeaker manually', () async {
      await service.initialize();
      final countAfterInit = mockController.androidAudioConfigCallCount;

      await service.setLoudspeaker();

      expect(
        mockController.androidAudioConfigCallCount,
        greaterThan(countAfterInit),
        reason: 'Android AEC must be re-applied on explicit loudspeaker switch',
      );
    });

    test('setAndroidAudioConfig is called when Bluetooth audio is configured', () async {
      mockController.setBluetoothConnected(true);
      await service.initialize();

      // At this point the route is Bluetooth → _setBluetoothAudio() must also
      // call setAndroidAudioConfig so AEC stays active regardless of routing.
      expect(
        mockController.androidAudioConfigCallCount,
        greaterThanOrEqualTo(1),
        reason: 'Android AEC must be configured for Bluetooth mode too',
      );
    });

    test('setAndroidAudioConfig is called when auto-detecting Bluetooth', () async {
      await service.initialize();

      mockController.setBluetoothConnected(true);
      final countBeforeBt = mockController.androidAudioConfigCallCount;
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(
        mockController.androidAudioConfigCallCount,
        greaterThan(countBeforeBt),
        reason: 'Switching to Bluetooth must also configure Android AEC',
      );
    });

    test('setAndroidAudioConfig is called when Bluetooth disconnects and reverts to loudspeaker', () async {
      mockController.setBluetoothConnected(true);
      await service.initialize();

      mockController.setBluetoothConnected(false);
      final countBeforeRevert = mockController.androidAudioConfigCallCount;
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(
        mockController.androidAudioConfigCallCount,
        greaterThan(countBeforeRevert),
        reason: 'Reverting to loudspeaker after Bluetooth disconnects must re-configure AEC',
      );
    });
  });
}
