import 'package:connectx/models/app_types.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/features/home/presentation/viewmodels/assistant_tab_view_model.dart';


import '../../../../helpers/test_helpers.mocks.dart';

void main() {
  late AssistantTabViewModel viewModel;
  late MockSpeechService mockSpeechService;

  setUp(() {
    mockSpeechService = MockSpeechService();
    viewModel = AssistantTabViewModel(speechService: mockSpeechService);
  });

  test('initialize sets up callbacks and status', () {
    // Act
    viewModel.initialize('Ready', 'en');

    // Assert
    expect(viewModel.statusText, 'Ready');
    verify(mockSpeechService.setLanguageCode('en')).called(1);
    
    // Check if callbacks were assigned. 
    // We verify the setter was called with ANY value (which should be the closure)
    verify(mockSpeechService.onSpeechStart = any);
    verify(mockSpeechService.onConnected = any);
    verify(mockSpeechService.onDataChannelOpen = any);
    verify(mockSpeechService.onSpeechEnd = any);
    verify(mockSpeechService.onDisconnected = any);
    verify(mockSpeechService.onChatMessage = any);
  });

  group('Callback tests', () {
      test('onSpeechStart updates state to listening', () {
         viewModel.initialize('Ready', 'en');
         
         final verification = verify(mockSpeechService.onSpeechStart = captureAny);
         final callback = verification.captured.first as OnSpeechStartCallback;
         
         // Act
         callback();
         
         // Assert
         expect(viewModel.conversationState, ConversationState.connecting);
      });
      
      test('onConnected clears status text', () {
         viewModel.initialize('Ready', 'en');
         final verification = verify(mockSpeechService.onConnected = captureAny);
         final callback = verification.captured.first as OnConnectedCallback;
         
         callback();
         expect(viewModel.statusText, isEmpty);
      });

      test('onChatMessage adds user message', () {
         viewModel.initialize('Ready', 'en');
         final verification = verify(mockSpeechService.onChatMessage = captureAny);
         final callback = verification.captured.first as OnChatMessageCallback;
         
         callback('Hello', true, false); // isUser=true
         
         expect(viewModel.chatMessages.length, 1);
         expect(viewModel.chatMessages.first.text, 'Hello');
         expect(viewModel.chatMessages.first.isUser, true);
         expect(viewModel.conversationState, ConversationState.processing);
      });

      test('onChatMessage adds AI message', () {
         viewModel.initialize('Ready', 'en');
         final verification = verify(mockSpeechService.onChatMessage = captureAny);
         final callback = verification.captured.first as OnChatMessageCallback;
         
         // Trigger user message first to set state
         callback('Hello', true, false);
         
         // Trigger AI message
         callback('Hi there', false, false);
         
         expect(viewModel.chatMessages.length, 2);
         expect(viewModel.chatMessages.last.text, 'Hi there');
         expect(viewModel.chatMessages.last.isUser, false);
         expect(viewModel.conversationState, ConversationState.listening);
      });
  });

  test('startChat calls speechService.startSpeech', () async {
    when(mockSpeechService.startSpeech(mode: anyNamed('mode')))
        .thenAnswer((_) async {});

    await viewModel.startChat();

    verify(mockSpeechService.startSpeech(mode: 'text')).called(1);
    expect(viewModel.error, null);
  });
  
  test('startChat handles errors', () async {
    when(mockSpeechService.startSpeech(mode: anyNamed('mode')))
        .thenThrow(Exception('Mic error'));

    await viewModel.startChat();

    verify(mockSpeechService.startSpeech(mode: 'text')).called(1);
    expect(viewModel.error, contains('Mic error'));
    expect(viewModel.conversationState, ConversationState.idle);
  });

  test('stopChat calls speechService.stopSpeech and resets state', () async {
    when(mockSpeechService.stopSpeech()).thenAnswer((_) async {});
    
    await viewModel.stopChat('Reset');
    
    verify(mockSpeechService.stopSpeech()).called(1);
    expect(viewModel.conversationState, ConversationState.idle);
    expect(viewModel.chatMessages, isEmpty);
    expect(viewModel.statusText, 'Reset');
  });

  test('dispose stops speech and cleans up callbacks', () {
    viewModel.dispose();

    verify(mockSpeechService.stopSpeech()).called(1);
    verify(mockSpeechService.onSpeechStart = null);
    verify(mockSpeechService.onConnected = null);
    verify(mockSpeechService.onDataChannelOpen = null);
    verify(mockSpeechService.onSpeechEnd = null);
    verify(mockSpeechService.onDisconnected = null);
    verify(mockSpeechService.onChatMessage = null);
  });
}
