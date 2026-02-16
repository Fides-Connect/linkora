import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:connectx/services/audio_routing_service.dart';

final Object? _skipOnAndroid = !kIsWeb && defaultTargetPlatform == TargetPlatform.android
    ? 'AudioRoutingService.initialize() requests runtime permissions on Android; '
      'these integration tests are skipped on Android to avoid permission dialogs '
      'that can hang or fail CI runs.'
    : false;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('AudioRoutingService Integration Tests', () {
    test(
      'initialize sets loudspeaker as default',
      () async {
        // This test runs on a real device/emulator with flutter_webrtc plugin
        final service = AudioRoutingService();
        
        // Should not throw an exception
        await service.initialize();
        
        // Should be using loudspeaker by default
        expect(service.isSpeakerOn, true);
        expect(service.getCurrentRouting(), AudioRouting.loudspeaker);
        
        // Clean up
        service.dispose();
      },
      skip: _skipOnAndroid,
    );

    test(
      'can manually switch to earpiece',
      () async {
        final service = AudioRoutingService();
        await service.initialize();
        
        // Switch to earpiece
        await service.setEarpiece();
        
        expect(service.isSpeakerOn, false);
        expect(service.getCurrentRouting(), AudioRouting.earpiece);
        
        service.dispose();
      },
      skip: _skipOnAndroid,
    );

    test(
      'can switch back to loudspeaker',
      () async {
        final service = AudioRoutingService();
        await service.initialize();
        
        // Switch to earpiece first
        await service.setEarpiece();
        expect(service.getCurrentRouting(), AudioRouting.earpiece);
        
        // Switch back to loudspeaker
        await service.setLoudspeaker();
        expect(service.isSpeakerOn, true);
        expect(service.getCurrentRouting(), AudioRouting.loudspeaker);
        
        service.dispose();
      },
      skip: _skipOnAndroid,
    );

    test(
      'callback is triggered on routing change',
      () async {
        final service = AudioRoutingService();
        await service.initialize();
        
        final routingChanges = <AudioRouting>[];
        service.onAudioRoutingChanged = (routing) {
          routingChanges.add(routing);
        };
        
        // Make some changes
        await service.setEarpiece();
        await service.setLoudspeaker();
        
        // Should have captured both changes
        expect(routingChanges, contains(AudioRouting.earpiece));
        expect(routingChanges, contains(AudioRouting.loudspeaker));
        expect(routingChanges.length, greaterThanOrEqualTo(2));
        
        service.dispose();
      },
      skip: _skipOnAndroid,
    );

    test('dispose cleans up properly', () {
      final service = AudioRoutingService();
      
      // Should not throw
      expect(() => service.dispose(), returnsNormally);
      
      // Should be safe to call multiple times
      expect(() => service.dispose(), returnsNormally);
      expect(() => service.dispose(), returnsNormally);
    });
  });
}
