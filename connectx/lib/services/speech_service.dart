import 'package:flutter_tts/flutter_tts.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
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
    _tts.setLanguage('en-US');
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
     final Future<Stream<List<int>>> stream = _recorder.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits, // LINEAR16
      bitRate: 16000 * 16, // 16kHz, 16bit
      sampleRate: 16000,
    ));

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

        audioStream.listen(
          (chunk) async {
            final audioBase64 = base64Encode(chunk);
            final url = 'https://speech.googleapis.com/v1/speech:recognize?key=$googleApiKey';
            final requestBody = {
              "config": {
                "encoding": "LINEAR16",
                "sampleRateHertz": 16000,
                "languageCode": "en-US",
                "enableAutomaticPunctuation": true
              },
              "audio": {"content": audioBase64}
            };

            final response = await http.post(
              Uri.parse(url),
              headers: {"Content-Type": "application/json"},
              body: jsonEncode(requestBody),
            );


            //onSpeechResult?.call("test :  ${response.statusCode}");
            if (response.statusCode == 200) {
              final data = jsonDecode(response.body);
              if (data['results'] != null &&
                  data['results'].isNotEmpty &&
                  data['results'][0]['alternatives'] != null &&
                  data['results'][0]['alternatives'].isNotEmpty) {
                final transcript = data['results'][0]['alternatives'][0]['transcript'] ?? '';
                onSpeechResult?.call(transcript);
              }
            }
          },
          onDone: () {
            _isListening = false;
            onSpeechEnd?.call();
          },
          onError: (e) {
            _isListening = false;
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