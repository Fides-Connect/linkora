import 'dart:async';
import 'dart:core';
import 'dart:io' show Platform;
import 'package:flutter/services.dart';

import 'package:google_speech/google_speech.dart';
import 'package:grpc/grpc.dart' hide Codec;
import 'package:connectx/generated/cloud_tts.pbgrpc.dart' as cloud_tts;
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:taudio/taudio.dart' as ta;

class SpeechService {
  // Recorder Services
  ta.FlutterSoundRecorder? _recorder;
  StreamController<Uint8List>? _recorderController;
  Stream<Uint8List>? _recorderStream;

  // Speech-to-Text components
  StreamSubscription? _speechRecognitionSubscription;
  SpeechToText? _speechToText;
  ClientChannel? _clientChannel;
  StreamingRecognitionConfig? _streamingConfig;

  // Text-to-Speech components
  ta.FlutterSoundPlayer? _player;
  StreamSubscription<cloud_tts.StreamingSynthesizeResponse>?
  _audioSynthesisSubscription;
  cloud_tts.TextToSpeechClient? _textToSpeech;

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function(String)? onSpeechResult;

  // Android audio-mode channel
  static const MethodChannel _audioModeChannel = MethodChannel(
    'connectx/audio_mode',
  );

  SpeechService();

  Future<void> stopSpeech() async {
    // Stop and clear recorder components
    await _recorder?.stopRecorder();
    await _recorder?.closeRecorder();
    await _recorderController?.close();
    await _recorderStream?.drain();
    _recorder = null;
    _recorderController = null;
    _recorderStream = null;

    // Stop and clear Speech-to-Text components
    await _speechRecognitionSubscription?.cancel();
    _speechToText?.dispose();
    await _clientChannel?.shutdown();
    _speechRecognitionSubscription = null;
    _speechToText = null;
    _clientChannel = null;
    _streamingConfig = null;

    // Stop and clear Text-to-Speech compnonents
    await _player?.stopPlayer();
    await _player?.closePlayer();
    await _audioSynthesisSubscription?.cancel();
    _player = null;
    _audioSynthesisSubscription = null;
    _textToSpeech = null;
  }

  /// Streams audio chunks to Google Speech-to-Text and updates live transcription.
  Future<void> startSpeech() async {
    onSpeechStart?.call();
    try {
      await _initialize();

      // Create a controller; pass its sink to taudio
      _recorderController = StreamController<Uint8List>.broadcast();
      _recorderStream = _recorderController!.stream;

      await _recorder!.startRecorder(
        codec: ta.Codec.pcm16,
        numChannels: 1,
        sampleRate: 16000,
        toStream: _recorderController!.sink,
        enableEchoCancellation: true
      );

      final responseStream = _speechToText!.streamingRecognize(
        _streamingConfig!,
        _recorderStream!,
      );

      _speechRecognitionSubscription = responseStream.listen(
        (data) async {
          // Cancel current audio synthesis and stop playback if new speech is detected
          try {
            print('New speech detected, stopping TTS playback if any.');
            //_audioSynthesisSubscription?.cancel();
            //_initializePlayer();
          } catch (e) {
            print('Error stopping TTS playback: $e');
          }

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
      print('Error in startSpeech: $e');
      onSpeechEnd?.call();
      rethrow;
    }
  }

  Future<void> _initialize() async {
    // Get OAuth Access Token from environment
    final accessToken = dotenv.env['OAUTH_ACCESS_TOKEN'] ?? '';
    if (accessToken.isEmpty) {
      throw Exception('Missing OAUTH_ACCESS_TOKEN environment variable');
    }

    // Android-specific audio mode setup
    if (Platform.isAndroid) {
      await _ensureAndroidCommMode();
    }

    // Initialize Speech Service Components
    if (_recorder == null) await _initializeRecorder();
    if (_speechToText == null) _initializeSpeechToText(accessToken);
    if (_textToSpeech == null) _initializeTextToSpeech(accessToken);
    if (_player == null) await _initializePlayer();

  }

  Future<void> _initializeRecorder() async {
    try {
      final microphoneRequest = await Permission.microphone.request();
      if (!microphoneRequest.isGranted) {
        throw Exception('Microphone permission denied');
      }
      _recorder = ta.FlutterSoundRecorder();
      await _recorder!.openRecorder();
    } catch (e) {
      print('Recorder initialization failed: $e');
      rethrow;
    }
  }

  Future<void> _ensureAndroidCommMode() async {
    try {
      final res = await _audioModeChannel.invokeMethod<Map>(
        'forceModeInCommunication',
      );
      print('Android audio mode set: $res');
    } catch (e) {
      print('Failed to set MODE_IN_COMMUNICATION: $e');
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

      _streamingConfig = StreamingRecognitionConfig(
        config: config,
        interimResults: false,
      );

      _speechToText = SpeechToText.viaToken('Bearer', accessToken);
    } catch (e) {
      print('Error initializing SpeechToText: $e');
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

    _textToSpeech = cloud_tts.TextToSpeechClient(
      _clientChannel!,
      options: CallOptions(metadata: {'Authorization': 'Bearer $accessToken'}),
    );
  }

  Future<void> _initializePlayer() async {
    _player = ta.FlutterSoundPlayer(voiceProcessing: false);
    await _player!.openPlayer();
    await _player!.startPlayerFromStream(
      codec: ta.Codec.pcm16,
      sampleRate: 16000,
      interleaved: true,
      bufferSize: 8192,
      numChannels: 1,
    );
  }

  void synthesizeSpeech(String text) {
    print('synthesizeSpeech called with text: $text');
    if (text.isNotEmpty) {
      final streamingSynthesizeConfig = cloud_tts.StreamingSynthesizeConfig(
        voice: cloud_tts.VoiceSelectionParams(
          languageCode: "de-DE",
          name: "de-DE-Chirp-HD-F",
        ),
        streamingAudioConfig: cloud_tts.StreamingAudioConfig(
          audioEncoding: cloud_tts.AudioEncoding.PCM,
          sampleRateHertz: 16000,
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

      final requestStream =
          Stream<cloud_tts.StreamingSynthesizeRequest>.fromIterable([
            requestConfig,
            requestText,
          ]);

      final responseStream = _textToSpeech?.streamingSynthesize(requestStream);

      _audioSynthesisSubscription = responseStream?.listen(
        (data) {
          final audioChunk = Uint8List.fromList(data.audioContent);
          _player?.uint8ListSink?.add(audioChunk);
        },
        onError: (e) {
          print('Error during TTS streaming: $e');
        },
        onDone: () {
          print('TTS streaming completed.');
        },
      );
    }
  }
}
