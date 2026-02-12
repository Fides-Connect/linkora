import 'package:flutter_test/flutter_test.dart';
import 'package:connectx/services/audio_routing_service.dart';
import '../mocks/mock_audio_hardware_controller.dart';

// Test timing constants for faster test execution
const testDeviceCheckInterval = Duration(milliseconds: 50);
const testInputChangeDebounce = Duration(milliseconds: 10);
// Wait duration accounts for device check interval + debounce + processing overhead
const testWaitDuration = Duration(milliseconds: 70);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AudioRoutingService - Initialization', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(hardwareController: mockController);
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
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('detects Bluetooth device connection', () async {
      await service.initialize();
      expect(service.isBluetoothConnected, false);

      // Set Bluetooth connected, which triggers device change callback
      mockController.setBluetoothConnected(true);
      
      // Wait for the device check to complete and debounce timer to fire
      await Future.delayed(testWaitDuration);

      expect(service.isBluetoothConnected, true);
    });

    test('selects Bluetooth audio output device when available', () async {
      await service.initialize();

      // Set Bluetooth connected, which triggers device change callback
      mockController.setBluetoothConnected(true);
      
      // Wait for the device check to complete and debounce timer to fire
      await Future.delayed(testWaitDuration);

      expect(mockController.selectedAudioOutputId, 'bluetooth-2');
    });

    test('routing automatically switches from loudspeaker to Bluetooth', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      // Set Bluetooth connected, which triggers device change callback
      mockController.setBluetoothConnected(true);
      
      // Wait for the device check to complete
      await Future.delayed(testWaitDuration);

      expect(service.getCurrentRouting(), AudioRouting.bluetooth);
    });

    test('hardware controller switches speakerphone OFF when Bluetooth connects', () async {
      await service.initialize();
      expect(mockController.speakerphoneOn, true);

      // Set Bluetooth connected, which triggers device change callback
      mockController.setBluetoothConnected(true);
      
      // Wait for the device check to complete
      await Future.delayed(testWaitDuration);

      expect(mockController.speakerphoneOn, false);
    });
  });

  group('AudioRoutingService - Manual Routing Control', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(hardwareController: mockController);
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

    test('is BluetoothConnected property accurately reflects Bluetooth status', () async {
      await service.initialize();
      expect(service.isBluetoothConnected, false);

      mockController.setBluetoothConnected(true);
      await Future.delayed(testWaitDuration);
      expect(service.isBluetoothConnected, true);

      mockController.setBluetoothConnected(false);
      await Future.delayed(testWaitDuration);
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
      await Future.delayed(testWaitDuration);
      expect(service.getCurrentRouting(), AudioRouting.bluetooth);
    });
  });
}
