import 'package:flutter/widgets.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:google_speech/google_speech.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:async';
import 'package:record/record.dart';

class SpeechService {
  late FlutterTts _tts;
  bool _isListening = false;
  bool _isSpeaking = false;
  final AudioRecorder _recorder = AudioRecorder();

  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function(String)? onSpeechResult;
  Function()? onTTSStart;
  Function()? onTTSEnd;

  SpeechService() {
    _initializeTTS();
  }

  void _initializeTTS() {
    _tts = FlutterTts();

    _tts.setStartHandler(() {
      _isSpeaking = true;
      onTTSStart?.call();
    });

    _tts.setCompletionHandler(() {
      _isSpeaking = false;
      onTTSEnd?.call();
    });

    _tts.setErrorHandler((msg) {
      _isSpeaking = false;
      onTTSEnd?.call();
    });

    // Configure TTS settings
    _tts.setLanguage('de-DE');
    _tts.setSpeechRate(0.5);
    _tts.setVolume(1.0);
    _tts.setPitch(1.0);
  }

  Future<bool> requestMicrophonePermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Starts recording and returns a live stream of PCM audio data from the microphone.
  Future<Stream<List<int>>> _recordAudio() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      throw Exception('Microphone permission denied');
    }

    // Start recording in PCM format (LINEAR16)
    final Future<Stream<List<int>>> stream = _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits, // LINEAR16
        bitRate: 16000 * 16, // 16kHz, 16bit
        sampleRate: 16000,
        numChannels: 1
      ),
    );

    // Return the audio stream
    return stream;
  }

  /// Streams audio chunks to Google Speech-to-Text and updates live transcription.
  Future<void> startListening() async {
    if (!_isListening && !_isSpeaking) {
      final hasPermission = await requestMicrophonePermission();
      if (!hasPermission) {
        throw Exception('Microphone permission denied');
      }

      _isListening = true;
      onSpeechStart?.call();

      try {
        final googleApiKey = dotenv.env['GEMINI_API_KEY'] ?? '';
        final audioStream = await _recordAudio();

        // Initial config
        final config = RecognitionConfig(
          encoding: AudioEncoding.LINEAR16,
          model: RecognitionModel.basic,
          enableAutomaticPunctuation: true,
          sampleRateHertz: 16000,
          languageCode: 'de-DE',
        );

        final streamingConfig = StreamingRecognitionConfig(
          config: config,
          interimResults: true,
        );

        final speechToText = SpeechToText.viaApiKey(googleApiKey);

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
            onSpeechEnd?.call();
          },
        );

      } catch (e) {
        onSpeechEnd?.call();
        rethrow;
      }
    }
  }

  Future<void> stopListening() async {
    if (_isListening) {
      _isListening = false;
      onSpeechEnd?.call();
    }
  }

  Future<void> speak(String text) async {
    if (!_isSpeaking && text.isNotEmpty) {
      await _tts.speak(text);
    }
  }

  Future<void> stopSpeaking() async {
    if (_isSpeaking) {
      await _tts.stop();
      _isSpeaking = false;
      onTTSEnd?.call();
    }
  }

  bool get isListening => _isListening;
  bool get isSpeaking => _isSpeaking;

  void dispose() {
    _tts.stop();
  }
}
