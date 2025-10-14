import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:permission_handler/permission_handler.dart';

class SpeechService {
  late FlutterTts _tts;
  late SpeechToText _speechToText;
  bool _isListening = false;
  bool _isSpeaking = false;
  
  // Callbacks
  Function()? onSpeechStart;
  Function()? onSpeechEnd;
  Function(String)? onSpeechResult;
  Function()? onTTSStart;
  Function()? onTTSEnd;
  
  SpeechService() {
    _initializeTTS();
    _initializeSpeechToText();
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
  
  void _initializeSpeechToText() {
    _speechToText = SpeechToText();
  }
  
  Future<bool> requestMicrophonePermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }
  
  Future<bool> initializeSpeechToText() async {
    return await _speechToText.initialize(
      onError: (error) {
        // Speech recognition error: $error (removed print for production)
        _isListening = false;
        onSpeechEnd?.call();
      },
      onStatus: (status) {
        // Speech recognition status: $status (removed print for production)
        if (status == 'done' || status == 'notListening') {
          _isListening = false;
          onSpeechEnd?.call();
        }
      },
    );
  }
  
  Future<void> startListening() async {
    if (!_isListening && !_isSpeaking) {
      final hasPermission = await requestMicrophonePermission();
      if (!hasPermission) {
        throw Exception('Microphone permission denied');
      }
      
      final initialized = await initializeSpeechToText();
      if (!initialized) {
        throw Exception('Speech recognition not available');
      }
      
      _isListening = true;
      onSpeechStart?.call();
      
      await _speechToText.listen(
        onResult: (result) {
          if (result.finalResult) {
            onSpeechResult?.call(result.recognizedWords);
          }
        },
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 3),
        listenOptions: SpeechListenOptions(
          partialResults: false,
          cancelOnError: true,
        ),
      );
    }
  }
  
  Future<void> stopListening() async {
    if (_isListening) {
      await _speechToText.stop();
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
    _speechToText.stop();
  }
}