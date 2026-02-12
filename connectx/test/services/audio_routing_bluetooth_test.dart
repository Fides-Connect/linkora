import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:connectx/services/audio_routing_service.dart';
import '../mocks/mock_audio_hardware_controller.dart';

/// Tests for Bluetooth speaker and microphone separation functionality
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AudioRoutingService - Bluetooth Speaker and Microphone Separation', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(hardwareController: mockController);
    });

    tearDown(() {
      service.dispose();
    });

    test('detects Bluetooth speaker and microphone separately', () async {
      await service.initialize();
      expect(service.isBluetoothSpeakerConnected, false);
      expect(service.isBluetoothMicrophoneConnected, false);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(service.isBluetoothSpeakerConnected, true);
        expect(service.isBluetoothMicrophoneConnected, true);
      });
    });

    test('reports any Bluetooth device connected via isBluetoothConnected', () async {
      await service.initialize();
      expect(service.isBluetoothConnected, false);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(service.isBluetoothConnected, true);
        expect(service.isBluetoothSpeakerConnected, true);
        expect(service.isBluetoothMicrophoneConnected, true);
      });
    });

    test('routes to Bluetooth when both speaker and mic are available', () async {
      await service.initialize();
      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(service.getCurrentRouting(), AudioRouting.bluetooth);
        expect(mockController.selectedAudioOutputId, 'bluetooth-2');
        expect(mockController.selectedAudioInputId, 'bluetooth-1');
      });
    });

    test('falls back to loudspeaker when Bluetooth disconnects', () async {
      await service.initialize();

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));
        expect(service.getCurrentRouting(), AudioRouting.bluetooth);

        mockController.setBluetoothConnected(false);
        async.elapse(Duration(milliseconds: 600));

        expect(service.getCurrentRouting(), AudioRouting.loudspeaker);
        expect(service.isBluetoothSpeakerConnected, false);
        expect(service.isBluetoothMicrophoneConnected, false);
        expect(mockController.speakerphoneOn, true);
      });
    });

    test('resets Bluetooth flags when switching to loudspeaker', () async {
      await service.initialize();

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        // Note: setLoudspeaker is async, so we need to await it outside fakeAsync
      });

      await service.setLoudspeaker();

      expect(service.isBluetoothSpeakerConnected, false);
      expect(service.isBluetoothMicrophoneConnected, false);
      expect(service.isSpeakerOn, true);
    });

    test('resets Bluetooth flags when switching to earpiece', () async {
      await service.initialize();

      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));
      });

      await service.setEarpiece();

      expect(service.isBluetoothSpeakerConnected, false);
      expect(service.isBluetoothMicrophoneConnected, false);
      expect(service.isSpeakerOn, false);
    });

    test('audio device enumeration checks both input and output types', () async {
      await service.initialize();

      // Trigger a device check
      await service.checkAndRouteAudio(forceUpdate: true);

      // Should enumerate both audiooutput and audioinput
      final types = mockController.enumerateTypes;
      expect(types.where((t) => t == 'audiooutput').length, greaterThan(0));
      expect(types.where((t) => t == 'audioinput').length, greaterThan(0));
    });
  });

  group('AudioRoutingService - Priority Logic', () {
    late MockAudioHardwareController mockController;
    late AudioRoutingService service;

    setUp(() {
      mockController = MockAudioHardwareController();
      service = AudioRoutingService(hardwareController: mockController);
    });

    tearDown(() {
      service.dispose();
    });

    test('priority 1: Bluetooth earphone when available', () async {
      await service.initialize();
      
      fakeAsync((async) {
        mockController.setBluetoothConnected(true);
        async.elapse(Duration(milliseconds: 600));

        expect(service.getCurrentRouting(), AudioRouting.bluetooth);
        expect(service.isBluetoothSpeakerConnected, true);
        expect(service.isBluetoothMicrophoneConnected, true);
      });
    });

    test('priority 2: Loudspeaker when no Bluetooth', () async {
      await service.initialize();
      mockController.setBluetoothConnected(false);
      await service.checkAndRouteAudio(forceUpdate: true);

      expect(service.getCurrentRouting(), AudioRouting.loudspeaker);
      expect(service.isSpeakerOn, true);
    });

    test('priority 3: Manual earpiece control', () async {
      await service.initialize();
      await service.setEarpiece();

      expect(service.getCurrentRouting(), AudioRouting.earpiece);
      expect(service.isSpeakerOn, false);
      expect(mockController.speakerphoneOn, false);
    });
  });
}
