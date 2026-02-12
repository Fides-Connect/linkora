import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:connectx/services/audio_routing_service.dart';
import '../mocks/mock_audio_hardware_controller.dart';

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
      service = AudioRoutingService(hardwareController: mockController);
    });

    tearDown(() {
      service.dispose();
    });

    test('detects Bluetooth device connection', () async {
      await service.initialize();
      expect(service.isBluetoothConnected, false);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(service.isBluetoothConnected, true);
      });
    });

    test('selects Bluetooth audio output device when available', () async {
      await service.initialize();

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(mockController.selectedAudioOutputId, 'bluetooth-2');
      });
    });

    test('routing automatically switches from loudspeaker to Bluetooth', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(service.getCurrentRouting(), AudioRouting.bluetooth);
      });
    });

    test('hardware controller switches speakerphone OFF when Bluetooth connects', () async {
      await service.initialize();
      expect(mockController.speakerphoneOn, true);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(mockController.speakerphoneOn, false);
      });
    });
  });

  group('AudioRoutingService - Manual Routing Control', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(hardwareController: mockController);
    });

    tearDown() {
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
      service = AudioRoutingService(hardwareController: mockController);
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

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));
        expect(service.isBluetoothConnected, true);

        mockController.setBluetoothConnected(false);
        async.elapse(Duration(milliseconds: 600));
        expect(service.isBluetoothConnected, false);
      });
    });

    test('getCurrentRouting returns correct AudioRouting enum value', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      await service.setEarpiece();
      expect(service.getCurrentRouting(), AudioRouting.earpiece);

      await service.setLoudspeaker();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));
        expect(service.getCurrentRouting(), AudioRouting.bluetooth);
      });
    });
  });
}
