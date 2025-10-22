import 'dart:core';
import 'dart:typed_data';

import 'package:google_speech/google_speech.dart';
import 'package:grpc/grpc.dart';
import 'package:connectx/generated/cloud_tts.pbgrpc.dart' as cloud_tts;
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_voice_engine/flutter_voice_engine.dart';

class SpeechService {
  final FlutterVoiceEngine _voiceEngine = FlutterVoiceEngine();

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function(String)? onSpeechResult;

  SpeechService();

  Future<bool> requestMicrophonePermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Starts recording and returns a live stream of PCM audio data from the microphone using Voice Engine.
  Future<Stream<List<int>>> _recordAudioWithVoiceEngine() async {
    try {
      // Initialize with custom config
      _voiceEngine.audioConfig = AudioConfig(
        sampleRate: 16000,
        channels: 1,
        bitDepth: 16,
        bufferSize: 4096,
        enableAEC: true,
      );

      _voiceEngine.sessionConfig = AudioSessionConfig(
        category: AudioCategory.playAndRecord,
        mode: AudioMode.voiceChat,
        options: {AudioOption.defaultToSpeaker},
      );

      await _voiceEngine.initialize();

      // Return the audio stream
      return _voiceEngine.audioChunkStream;
    } catch (e) {
      print('VoiceEngine initialization failed: $e');
      rethrow;
    }
  }

  /// Streams audio chunks to Google Speech-to-Text and updates live transcription.
  Future<void> startListening() async {
    final hasPermission = await requestMicrophonePermission();
    if (!hasPermission) {
      throw Exception('Microphone permission denied');
    }

    onSpeechStart?.call();

    try {
      final accessToken = dotenv.env['OAUTH_ACCESS_TOKEN'] ?? '';
      final audioStream = await _recordAudioWithVoiceEngine();

      print("Access Token: $accessToken");

      // Initial config
      final config = RecognitionConfig(
        encoding: AudioEncoding.LINEAR16,
        model: RecognitionModel.basic,
        enableAutomaticPunctuation: true,
        sampleRateHertz: 16000,
        languageCode: 'de-DE',
        audioChannelCount: 1,
      );

      final streamingConfig = StreamingRecognitionConfig(
        config: config,
        interimResults: false,
      );

      final speechToText = SpeechToText.viaToken('Bearer', accessToken);

      final responseStream = speechToText.streamingRecognize(
        streamingConfig,
        audioStream,
      );

      responseStream.listen(
        (data) {
          // Extract transcript from data and callback
          final transcript = data.results
              .map((result) => result.alternatives.first.transcript)
              .join(' ');
          onSpeechResult?.call(transcript);
        },
        onError: (e) {
          print( 'Error during speech recognition: $e');
          onSpeechEnd?.call();
        },
      );

      await _voiceEngine.startRecording();

      // Listen for errors
      _voiceEngine.errorStream.listen((error) {
        print('Error at Voice Engine: $error');
      });
    } catch (e) {
      print('Error in startListening: $e');
      onSpeechEnd?.call();
      rethrow;
    }
  }

  Future<void> speak(String text) async {
    print('TTS speak called with text: $text');
    if (text.isNotEmpty) {
      final String accessToken = dotenv.env['OAUTH_ACCESS_TOKEN'] ?? '';

      print("Access Token: $accessToken");

      final channel = ClientChannel(
        'texttospeech.googleapis.com',
        port: 443,
        options: const ChannelOptions(credentials: ChannelCredentials.secure()),
      );

      final stub = cloud_tts.TextToSpeechClient(
        channel,
        options: CallOptions(
          metadata: {'Authorization': 'Bearer $accessToken'},
        ),
      );

      final streamingSynthesizeConfig = cloud_tts.StreamingSynthesizeConfig(
        voice: cloud_tts.VoiceSelectionParams(
          languageCode: "de-DE",
          name: "de-DE-Chirp-HD-F",
        ),
        streamingAudioConfig: cloud_tts.StreamingAudioConfig(
          audioEncoding: cloud_tts.AudioEncoding.PCM,
          sampleRateHertz: 24000,
        ),
      );

      final streamingSynthesisInput = cloud_tts.StreamingSynthesisInput(
        text: text,
      );

      final requestConfig = cloud_tts.StreamingSynthesizeRequest(
        streamingConfig: streamingSynthesizeConfig,
      );

      final requestText = cloud_tts.StreamingSynthesizeRequest(
        input: streamingSynthesisInput,
      );

      final requestStream =
          Stream<cloud_tts.StreamingSynthesizeRequest>.fromIterable([
            requestConfig,
            requestText,
          ]);

      final responseStream = stub.streamingSynthesize(requestStream);

      await for (var response in responseStream) {
        // Each response.audioChunk contains a chunk of audio bytes
        final audioChunk = Uint8List.fromList(response.audioContent);
        // Play audioChunk
        _voiceEngine.playAudioChunk(audioChunk);
      }
      await channel.shutdown();
    }
  }
}
