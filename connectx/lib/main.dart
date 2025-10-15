import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'widgets/particle_sphere.dart';
import 'services/gemini_service.dart';
import 'services/speech_service.dart';

import 'package:permission_handler/permission_handler.dart';

void main() {
  runApp(const ConnectXApp());
}

class ConnectXApp extends StatelessWidget {
  const ConnectXApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ConnectX',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6C63FF),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF0A0A0A),
      ),
      home: const ConnectXHomePage(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class ConnectXHomePage extends StatefulWidget {
  const ConnectXHomePage({super.key});

  @override
  State<ConnectXHomePage> createState() => _ConnectXHomePageState();
}

class _ConnectXHomePageState extends State<ConnectXHomePage> {
  late GeminiService _geminiService;
  late SpeechService _speechService;
  
  bool _isAnimating = false;
  bool _isListening = false;
  String _currentMessage = '';
  String _statusText = 'Tap the microphone to start speaking';
  
  @override
  void initState() {
    super.initState();
    _initializeServices();
  }
  
  void _initializeServices() {
    _geminiService = GeminiService();
    _speechService = SpeechService();
    
    // Set up speech service callbacks
    _speechService.onSpeechStart = () {
      setState(() {
        _isListening = true;
        _isAnimating = true;
        _statusText = 'Listening...';
      });
    };
    
    _speechService.onSpeechEnd = () {
      setState(() {
        _isListening = false;
        _isAnimating = false;
        _statusText = 'Processing...';
      });
    };
    
    _speechService.onSpeechResult = (String result) {
      _handleSpeechResult(result);
    };
    
    _speechService.onTTSStart = () {
      setState(() {
        _isAnimating = true;
        _statusText = 'Speaking...';
      });
    };
    
    _speechService.onTTSEnd = () {
      setState(() {
        _isAnimating = false;
        _statusText = 'Tap the microphone to start speaking';
      });
    };
  }
  
  void _handleSpeechResult(String spokenText) async {
    if (spokenText.isNotEmpty) {
      setState(() {
        _currentMessage = spokenText;
        _statusText = 'Getting response from Gemini...';
      });
      
      try {
        final response = await _geminiService.generateResponse(spokenText);
        await _speechService.speak(response);
      } catch (e) {
        setState(() {
          _statusText = 'Error: ${e.toString()}';
        });
      }
    }
  }
  
  void _startListening() async {
    try {// Request microphone permission
      await Permission.microphone.request();
      await _speechService.startListening();
    } catch (e) {
      setState(() {
        _statusText = 'Error: ${e.toString()}';
      });
    }
  }
  
  void _stopChat() async {
    await _speechService.stopListening();
    await _speechService.stopSpeaking();
    
    setState(() {
      _isListening = false;
      _isAnimating = false;
      _currentMessage = '';
      _statusText = 'Chat stopped. Tap the microphone to start again.';
    });
    
    // Provide haptic feedback
    HapticFeedback.mediumImpact();
  }
  
  @override
  void dispose() {
    _speechService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            // Background gradient
            Container(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment.center,
                  radius: 1.5,
                  colors: [
                    Color(0xFF1A1A2E),
                    Color(0xFF0A0A0A),
                  ],
                ),
              ),
            ),
            
            // Main content
            Column(
              children: [
                // Status bar
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Text(
                        'ConnectX',
                        style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          color: const Color(0xFF6C63FF),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        _statusText,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.white70,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
                
                // Particle sphere in the center
                Expanded(
                  child: Center(
                    child: ParticleSphere(
                      isAnimating: _isAnimating,
                      radius: 120,
                      particleCount: 80,
                      primaryColor: const Color(0xFF6C63FF),
                      secondaryColor: const Color(0xFF00D4FF),
                    ),
                  ),
                ),
                
                // Current message display
                if (_currentMessage.isNotEmpty)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.all(20),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: const Color(0xFF6C63FF).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Text(
                      _currentMessage,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
              ],
            ),
            
            // Bottom action buttons
            Positioned(
              bottom: 40,
              left: 40,
              child: FloatingActionButton(
                onPressed: _stopChat,
                backgroundColor: Colors.red.withValues(alpha: 0.8),
                heroTag: 'stop_button',
                child: const Icon(
                  Icons.stop,
                  color: Colors.white,
                ),
              ),
            ),
            
            Positioned(
              bottom: 40,
              right: 40,
              child: FloatingActionButton.large(
                onPressed: _isListening ? null : _startListening,
                backgroundColor: _isListening 
                    ? const Color(0xFF6C63FF).withValues(alpha: 0.5)
                    : const Color(0xFF6C63FF),
                heroTag: 'mic_button',
                child: Icon(
                  _isListening ? Icons.mic : Icons.mic_none,
                  color: Colors.white,
                  size: 32,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
