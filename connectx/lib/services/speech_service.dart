import 'dart:core';
import 'dart:typed_data';

import 'package:google_speech/google_speech.dart';
import 'package:grpc/grpc.dart';
import 'package:connectx/generated/cloud_tts.pbgrpc.dart' as cloud_tts;
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_voice_engine/flutter_voice_engine.dart';

class SpeechService {
  FlutterVoiceEngine? _voiceEngine;
  cloud_tts.TextToSpeechClient? _ttsClient;
  ClientChannel? _clientChannel;

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function(String)? onSpeechResult;

  SpeechService();

  Future<void> initialize() async {
    // Get OAuth Access Token from environment
    final accessToken = dotenv.env['OAUTH_ACCESS_TOKEN'] ?? '';
    print("Access Token: $accessToken");

    // Initialize Speech Service Components
    await _initializeVoiceEngine();
    _initializeSpeechToText(accessToken);
    _initializeTextToSpeech(accessToken);
  }

  Future<void> _initializeVoiceEngine() async {
    try {
      final microphoneRequest = await Permission.microphone.request();
      if (!microphoneRequest.isGranted) {
        throw Exception('Microphone permission denied');
      }

      // Initialize with custom config
      _voiceEngine = FlutterVoiceEngine();
      _voiceEngine?.audioConfig = AudioConfig(
        sampleRate: 16000,
        channels: 1,
        bitDepth: 16,
        bufferSize: 4096,
        enableAEC: true,
      );

      _voiceEngine?.sessionConfig = AudioSessionConfig(
        category: AudioCategory.playAndRecord,
        mode: AudioMode.spokenAudio,
        options: {AudioOption.defaultToSpeaker},
      );
      // Listen for errors
      _voiceEngine?.errorStream.listen((error) {
        print('Error at Voice Engine: $error');
      });
      await _voiceEngine?.initialize();
    } catch (e) {
      print('VoiceEngine initialization failed: $e');
      rethrow;
    }
  }

  void _initializeSpeechToText(String accessToken) {
    try {
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
        _voiceEngine!.audioChunkStream,
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
          print('Error during speech recognition: $e');
          onSpeechEnd?.call();
        },
      );
    } catch (e) {
      print('Error in startListening: $e');
      onSpeechEnd?.call();
      rethrow;
    }
  }

  void _initializeTextToSpeech(String accessToken) {
    _clientChannel = ClientChannel(
      'texttospeech.googleapis.com',
      port: 443,
      options: const ChannelOptions(credentials: ChannelCredentials.secure()),
    );

    _ttsClient = cloud_tts.TextToSpeechClient(
      _clientChannel!,
      options: CallOptions(metadata: {'Authorization': 'Bearer $accessToken'}),
    );
  }

  Future<void> dispose() async {
    // Shutdoown resources
    await _voiceEngine?.shutdownAll();
    await _clientChannel?.shutdown();

    // Clear references
    _voiceEngine = null;
    _ttsClient = null;
    _clientChannel = null;
  }

  /// Streams audio chunks to Google Speech-to-Text and updates live transcription.
  Future<void> startSpeech() async {
    onSpeechStart?.call();
    try {
      await _voiceEngine?.startRecording();
    } catch (e) {
      print('Error in startListening: $e');
      onSpeechEnd?.call();
      rethrow;
    }
  }

  Future<void> speak(String text) async {
    print('TTS speak called with text: $text');
    if (text.isNotEmpty) {
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

      final requestConfig = cloud_tts.StreamingSynthesizeRequest(
        streamingConfig: streamingSynthesizeConfig,
      );

      final streamingSynthesisInput = cloud_tts.StreamingSynthesisInput(
        text: text,
      );

      final requestText = cloud_tts.StreamingSynthesizeRequest(
        input: streamingSynthesisInput,
      );

      final requestStreamText =
          Stream<cloud_tts.StreamingSynthesizeRequest>.fromIterable([
            requestConfig,
            requestText,
          ]);

      final responseStream = _ttsClient!.streamingSynthesize(requestStreamText);

      await for (var response in responseStream) {
        // Each response.audioChunk contains a chunk of audio bytes
        final audioChunk = Uint8List.fromList(response.audioContent);
        // Play audioChunk
        _voiceEngine?.playAudioChunk(audioChunk);
      }
    }
  }
}
