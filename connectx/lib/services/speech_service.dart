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
  // Replace 'record' with taudio recorder + stream controller
  ta.FlutterSoundRecorder? _recorder;
  StreamController<Uint8List>? _recorderController;
  Stream<Uint8List>? _recorderStream;
  StreamSubscription? _speechRecognitionSubscription;
  SpeechToText? _speechToText;
  cloud_tts.TextToSpeechClient? _textToSpeech;
  ClientChannel? _clientChannel;
  StreamSubscription<cloud_tts.StreamingSynthesizeResponse>?
  _audioSynthesisSubscription;
  StreamingRecognitionConfig? _streamingConfig;
  ta.FlutterSoundPlayer? _player;

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
    // stop taudio player if started
    _audioSynthesisSubscription?.cancel();
    await _player?.stopPlayer();
    await _player?.closePlayer();
    _audioSynthesisSubscription = null;
    _player = null;

    // Shutdown resources
    await _recorder?.stopRecorder();
    await _recorder?.closeRecorder();
    await _recorderController?.close();
    _recorder = null;
    _recorderController = null;
    _recorderStream = null;

    // Cancel recognition subscription
    await _speechRecognitionSubscription?.cancel();
    _speechRecognitionSubscription = null;
    _speechToText?.dispose();
    await _clientChannel?.shutdown();

    _speechToText = null;
    _textToSpeech = null;
    _clientChannel = null;
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
        enableEchoCancellation: true,
        enableNoiseSuppression: true,
      );

      // Inspect after starting recorder
      // Small delay to allow the system to reflect active configs
      Future.delayed(const Duration(milliseconds: 150), () {
        _logActiveRecordingConfigs('afterStart');
      });

      final responseStream = _speechToText!.streamingRecognize(
        _streamingConfig!,
        _recorderStream!,
      );

      _speechRecognitionSubscription = responseStream.listen(
        (data) async {
          // Cancel current audio synthesis and stop playback if new speech is detected
          try {
            print('New speech detected, stopping TTS playback if any.');
            _audioSynthesisSubscription?.cancel();
            if (_player != null) {
              await _player?.stopPlayer();
              await _initializePlayer();
              print("Stopped TTS playback.");
            }
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
      // ignore: avoid_print
      print('Android audio mode set: $res');
    } catch (e) {
      // ignore: avoid_print
      print('Failed to set MODE_IN_COMMUNICATION: $e');
    }
  }

  Future<void> _logActiveRecordingConfigs([String tag = '']) async {
    if (!Platform.isAndroid) return;
    try {
      final configs = await _audioModeChannel.invokeMethod<List>(
        'getActiveRecordingConfigurations',
      );
      // ignore: avoid_print
      print('ActiveRecordingConfigurations $tag: ${configs ?? []}');
    } catch (e) {
      // ignore: avoid_print
      print('Error fetching recording configs: $e');
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
      // streamingRecognize will be started when the recorder stream is available
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
    // Open taudio player once; we'll use fromDataBuffer for playback
    if (_player == null) {
      _player = ta.FlutterSoundPlayer(voiceProcessing: false);
      await _player!.openPlayer();
    }

    await _player!.startPlayerFromStream(
      codec: ta.Codec.pcm16,
      sampleRate: 16000,
      interleaved: true,
      bufferSize: 512,
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
          if (audioChunk.isNotEmpty) {
            _player?.uint8ListSink?.add(audioChunk);
          }
        },
        onError: (e) {
          // ignore: avoid_print
          print('Error during TTS streaming: $e');
        },
        onDone: () {
          print('TTS streaming completed.');
        },
      );
    }
  }
}
