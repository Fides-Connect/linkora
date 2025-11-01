import 'dart:async';
import 'dart:core';
import 'dart:typed_data';

import 'package:google_speech/google_speech.dart';
import 'package:grpc/grpc.dart';
import 'package:connectx/generated/cloud_tts.pbgrpc.dart' as cloud_tts;
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:record/record.dart';
import 'package:sound_stream/sound_stream.dart';

class SpeechService {
  AudioRecorder? _recorder;
  Stream<Uint8List>? _recorderStream;
  StreamSubscription? _speechRecognitionSubscription;
  SpeechToText? _speechToText;
  cloud_tts.TextToSpeechClient? _textToSpeech;
  ClientChannel? _clientChannel;
  StreamSubscription<cloud_tts.StreamingSynthesizeResponse>?
  _audioSynthesisSubscription;
  StreamingRecognitionConfig? _streamingConfig;
  PlayerStream? _player;

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function(String)? onSpeechResult;

  SpeechService();

  Future<void> stopSpeech() async {
    // Shutdown resources
    await _recorder?.stop();
    _recorderStream = null;
    // Cancel recognition subscription
    await _speechRecognitionSubscription?.cancel();
    _speechRecognitionSubscription = null;
    _speechToText?.dispose();
    await _clientChannel?.shutdown();

    // stop sound_stream player if started
    await _player?.stop();

    _speechToText = null;
    _textToSpeech = null;
    _clientChannel = null;
    _player = null;
  }

  /// Streams audio chunks to Google Speech-to-Text and updates live transcription.
  Future<void> startSpeech() async {
    onSpeechStart?.call();
    try {
      await _initialize();
      // Start recording stream using `record` and connect to Google Speech
      final recordConfig = RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: true,
        echoCancel: true,
        noiseSuppress: true,
      );
      _recorderStream = await _recorder!.startStream(recordConfig);

      final responseStream = _speechToText!.streamingRecognize(
        _streamingConfig!,
        _recorderStream!,
      );

      _speechRecognitionSubscription = responseStream.listen(
        (data) {
          // Cancel current audio synthesis if new speech is detected
          _audioSynthesisSubscription?.cancel();
          //_player?.stop();

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

      _recorder = AudioRecorder();
      // No additional audio config here — Record.startStream() provides PCM bytes.
    } catch (e) {
      print('Recorder initialization failed: $e');
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
    // Ensure sound_stream player is initialized and started for PCM playback.
    _player = PlayerStream();
    await _player!.initialize(sampleRate: 16000);
    await _player!.start();
    await _player!.usePhoneSpeaker(true);
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
          // Handle each audio chunk as it arrives
          final audioChunk = Uint8List.fromList(data.audioContent);
          // Feed raw PCM bytes into sound_stream player
          _player!.writeChunk(audioChunk);
        },
        onError: (e) {
          print('Error during TTS streaming: $e');
        },
      );
    }
  }
}
