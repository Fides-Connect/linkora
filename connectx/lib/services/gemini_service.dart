import 'package:google_generative_ai/google_generative_ai.dart';

class GeminiService {
  static const String _apiKey = 'YOUR_API_KEY_HERE'; // Replace with your actual API key
  late GenerativeModel _model;
  
  GeminiService() {
    _model = GenerativeModel(
      model: 'gemini-pro',
      apiKey: _apiKey,
    );
  }
  
  Future<String> generateResponse(String prompt) async {
    try {
      if (_apiKey == 'YOUR_API_KEY_HERE') {
        return 'Please set your Google Gemini API key in lib/services/gemini_service.dart';
      }
      
      final content = [Content.text(prompt)];
      final response = await _model.generateContent(content);
      
      return response.text ?? 'Sorry, I could not generate a response.';
    } catch (e) {
      return 'Error: ${e.toString()}';
    }
  }
  
  Stream<String> generateResponseStream(String prompt) async* {
    try {
      if (_apiKey == 'YOUR_API_KEY_HERE') {
        yield 'Please set your Google Gemini API key in lib/services/gemini_service.dart';
        return;
      }
      
      final content = [Content.text(prompt)];
      final response = _model.generateContentStream(content);
      
      await for (final chunk in response) {
        yield chunk.text ?? '';
      }
    } catch (e) {
      yield 'Error: ${e.toString()}';
    }
  }
}