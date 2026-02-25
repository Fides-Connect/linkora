import 'dart:async';

import 'package:connectx/models/app_types.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:connectx/features/home/presentation/viewmodels/assistant_tab_view_model.dart';
import '../../../../helpers/test_helpers.mocks.dart';

void main() {
  late AssistantTabViewModel vm;
  late MockSpeechService mockSpeech;

  setUp(() {
    mockSpeech = MockSpeechService();
    vm = AssistantTabViewModel(speechService: mockSpeech);
  });

  tearDown(() {
    vm.dispose();
  });

  // ── helpers ────────────────────────────────────────────────────────────────

  /// Call initialize() and return all captured callbacks by name.
  Map<String, dynamic> init({String status = 'Ready', String lang = 'en'}) {
    vm.initialize(status, lang);
    final speechStartCb = verify(
      mockSpeech.onSpeechStart = captureAny,
    ).captured.last as OnSpeechStartCallback;
    final connectedCb = verify(
      mockSpeech.onConnected = captureAny,
    ).captured.last as OnConnectedCallback;
    final dataChannelOpenCb = verify(
      mockSpeech.onDataChannelOpen = captureAny,
    ).captured.last as Function();
    final chatCb = verify(
      mockSpeech.onChatMessage = captureAny,
    ).captured.last as OnChatMessageCallback;
    final runtimeStateCb = verify(
      mockSpeech.onRuntimeState = captureAny,
    ).captured.last as OnRuntimeStateCallback;
    return {
      'speechStart': speechStartCb,
      'connected': connectedCb,
      'dataChannelOpen': dataChannelOpenCb,
      'chat': chatCb,
      'runtimeState': runtimeStateCb,
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // startChat() — voice vs text mode
  // ══════════════════════════════════════════════════════════════════════════

  group('startChat() mode selection', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
    });

    test('defaults to text mode (mode=text)', () async {
      await vm.startChat();
      verify(mockSpeech.startSpeech(mode: 'text')).called(1);
    });

    test('voice mode passes mode=voice', () async {
      await vm.startChat(voiceMode: true);
      verify(mockSpeech.startSpeech(mode: 'voice')).called(1);
    });

    test('isVoiceMode reflects requested mode', () async {
      await vm.startChat(voiceMode: true);
      expect(vm.isVoiceMode, isTrue);

      await vm.stopChat('r');
      await vm.startChat(voiceMode: false);
      expect(vm.isVoiceMode, isFalse);
    });

    test('does not unmute mic for text sessions after start', () async {
      await vm.startChat(voiceMode: false);
      verifyNever(mockSpeech.setMicrophoneMuted(false));
    });
  });

  group('startChat() pendingText — optimistic message', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
    });

    test('adds pending text to chat history immediately', () async {
      await vm.startChat(voiceMode: false, pendingText: 'Hello AI');
      expect(vm.chatMessages.length, 1);
      expect(vm.chatMessages.first.text, 'Hello AI');
      expect(vm.chatMessages.first.isUser, isTrue);
    });

    test('sets state to connecting when pendingText given', () async {
      await vm.startChat(voiceMode: false, pendingText: 'Hi');
      expect(vm.conversationState, ConversationState.connecting);
    });

    test('trims pendingText before adding', () async {
      await vm.startChat(voiceMode: false, pendingText: '  trimmed  ');
      expect(vm.chatMessages.first.text, 'trimmed');
    });
  });

  group('startChat() error handling', () {
    test('resets to idle and stores error when startSpeech throws', () async {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenThrow(Exception('Mic denied'));
      await vm.startChat(voiceMode: false);
      expect(vm.error, contains('Mic denied'));
      expect(vm.conversationState, ConversationState.idle);
      expect(vm.isVoiceMode, isFalse);
    });

    test('is no-op when session already active', () async {
      // Use a completer so we can fire the second startChat while the first is
      // still in-flight (i.e. _isStarting is true).
      final completer = Completer<void>();
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) => completer.future);

      final first = vm.startChat(voiceMode: false);
      // Second call fires while _isStarting == true
      await vm.startChat(voiceMode: true);

      completer.complete();
      await first;

      // startSpeech must only have been called once
      verify(mockSpeech.startSpeech(mode: anyNamed('mode'))).called(1);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // Data-channel readiness (dual-gate dedup)
  // ══════════════════════════════════════════════════════════════════════════

  group('data channel readiness — pending message flush', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      when(mockSpeech.sendTextMessage(any)).thenReturn(true);
    });

    test('flushes pending text message when onDataChannelOpen fires', () async {
      final cbs = init();
      await vm.startChat(voiceMode: false, pendingText: 'flush me');
      (cbs['dataChannelOpen'] as Function())();
      verify(mockSpeech.sendTextMessage('flush me')).called(1);
    });

    // Regression test: onConnected fires when RTCPeerConnectionStateConnected is
    // reached, which is BEFORE the SCTP data channel is "open".  Calling
    // _onDataChannelReady() there used to drop the pending message (channel not
    // open) and set _dataChannelReady=true so the real onDataChannelOpen was
    // ignored.  The correct gate is onDataChannelOpen only.
    test(
        'onConnected alone does NOT flush pending message '
        '(channel may not be open yet — real race on device)',
        () async {
      final cbs = init();
      await vm.startChat(voiceMode: false, pendingText: 'not yet');
      // Only onConnected fires (data channel still connecting)
      (cbs['connected'] as Function())();
      verifyNever(mockSpeech.sendTextMessage(any));

      // Now the data channel truly opens — message must be sent exactly once
      (cbs['dataChannelOpen'] as Function())();
      verify(mockSpeech.sendTextMessage('not yet')).called(1);
    });

    test('dedup: onConnected + onDataChannelOpen together flush exactly once',
        () async {
      final cbs = init();
      await vm.startChat(voiceMode: false, pendingText: 'once');
      (cbs['connected'] as Function())();
      (cbs['dataChannelOpen'] as Function())();
      verify(mockSpeech.sendTextMessage('once')).called(1);
    });

    test('no pending message → sendTextMessage not called on channel open',
        () async {
      final cbs = init();
      await vm.startChat(voiceMode: false);
      (cbs['dataChannelOpen'] as Function())();
      verifyNever(mockSpeech.sendTextMessage(any));
    });
  });

  group('data channel readiness — mic state', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
    });

    test('unmutes mic for voice sessions when channel opens', () async {
      final cbs = init();
      await vm.startChat(voiceMode: true);
      clearInteractions(mockSpeech);
      (cbs['dataChannelOpen'] as Function())();
      verify(mockSpeech.setMicrophoneMuted(false)).called(greaterThanOrEqualTo(1));
    });

    test('does not unmute mic for text sessions when channel opens', () async {
      final cbs = init();
      await vm.startChat(voiceMode: false);
      clearInteractions(mockSpeech);
      (cbs['dataChannelOpen'] as Function())();
      verifyNever(mockSpeech.setMicrophoneMuted(false));
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // sendTextMessage()
  // ══════════════════════════════════════════════════════════════════════════

  group('sendTextMessage()', () {
    late Map<String, dynamic> cbs;

    setUp(() async {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      when(mockSpeech.sendTextMessage(any)).thenReturn(true);
      cbs = init();
      await vm.startChat(voiceMode: false);
      (cbs['dataChannelOpen'] as Function())(); // channel is ready
    });

    test('optimistically adds message to chat before sending', () {
      vm.sendTextMessage('hey there');
      expect(
          vm.chatMessages.any((m) => m.text == 'hey there' && m.isUser), isTrue);
    });

    test('sets state to processing', () {
      vm.sendTextMessage('process me');
      expect(vm.conversationState, ConversationState.processing);
    });

    test('delegates to speechService.sendTextMessage', () {
      vm.sendTextMessage('delegate this');
      verify(mockSpeech.sendTextMessage('delegate this')).called(1);
    });

    test('ignores empty string', () {
      vm.sendTextMessage('');
      verifyNever(mockSpeech.sendTextMessage(any));
    });

    test('ignores whitespace-only string', () {
      vm.sendTextMessage('   ');
      verifyNever(mockSpeech.sendTextMessage(any));
    });
  });

  group('sendTextMessage() when channel not ready', () {
    test('sets error and does not send', () async {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      init();
      // channel never opened
      vm.sendTextMessage('too early');
      expect(vm.error, isNotNull);
      expect(vm.error, contains('not ready'));
      verifyNever(mockSpeech.sendTextMessage(any));
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // onChatMessage — user message echo deduplication
  // ══════════════════════════════════════════════════════════════════════════

  group('onChatMessage echo dedup', () {
    late Map<String, dynamic> cbs;

    setUp(() async {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      when(mockSpeech.sendTextMessage(any)).thenReturn(true);
      cbs = init();
      await vm.startChat(voiceMode: false);
      (cbs['dataChannelOpen'] as Function())();
    });

    test('server echo of optimistic user message is not re-added', () {
      vm.sendTextMessage('dup me');
      final countBefore = vm.chatMessages.length;
      (cbs['chat'] as OnChatMessageCallback)('dup me', true, false);
      expect(vm.chatMessages.length, countBefore);
    });

    test('different text from server IS added as a new message', () {
      vm.sendTextMessage('my question');
      (cbs['chat'] as OnChatMessageCallback)('server version', true, false);
      expect(
        vm.chatMessages.where((m) => m.isUser).map((m) => m.text).toList(),
        contains('server version'),
      );
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // AI streaming chunk assembly
  // ══════════════════════════════════════════════════════════════════════════

  group('AI streaming chunks', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
    });

    test('isChunk=true fragments are appended to the last AI message', () async {
      final cbs = init();
      await vm.startChat();
      (cbs['connected'] as Function())();

      (cbs['chat'] as OnChatMessageCallback)('Q', true, false);
      (cbs['chat'] as OnChatMessageCallback)('Hello ', false, true);
      (cbs['chat'] as OnChatMessageCallback)('world!', false, true);

      final aiMsg = vm.chatMessages.lastWhere((m) => !m.isUser);
      expect(aiMsg.text, 'Hello world!');
    });

    test('new user message starts a fresh AI bubble', () async {
      final cbs = init();
      await vm.startChat();
      (cbs['connected'] as Function())();

      (cbs['chat'] as OnChatMessageCallback)('Q1', true, false);
      (cbs['chat'] as OnChatMessageCallback)('A1', false, false);
      (cbs['chat'] as OnChatMessageCallback)('Q2', true, false);
      (cbs['chat'] as OnChatMessageCallback)('A2', false, false);

      expect(vm.chatMessages.length, 4);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // switchToTextMode()
  // ══════════════════════════════════════════════════════════════════════════

  group('switchToTextMode()', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
    });

    test('mutes microphone', () async {
      await vm.startChat(voiceMode: true);
      clearInteractions(mockSpeech);
      vm.switchToTextMode();
      verify(mockSpeech.setMicrophoneMuted(true)).called(1);
    });

    test('sets isVoiceMode to false', () async {
      await vm.startChat(voiceMode: true);
      vm.switchToTextMode();
      expect(vm.isVoiceMode, isFalse);
    });

    test('notifies server via notifyModeSwitch("text")', () async {
      await vm.startChat(voiceMode: true);
      vm.switchToTextMode();
      verify(mockSpeech.notifyModeSwitch('text')).called(1);
    });

    test('is no-op when already in text mode', () async {
      await vm.startChat(voiceMode: false);
      clearInteractions(mockSpeech);
      vm.switchToTextMode();
      verifyNever(mockSpeech.notifyModeSwitch(any));
      verifyNever(mockSpeech.setMicrophoneMuted(any));
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // switchToVoiceMode()
  // ══════════════════════════════════════════════════════════════════════════

  group('switchToVoiceMode()', () {
    setUp(() {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
    });

    test('calls enableVoiceMode on speech service', () async {
      when(mockSpeech.enableVoiceMode()).thenAnswer((_) async {});
      await vm.startChat(voiceMode: false);
      await vm.switchToVoiceMode();
      verify(mockSpeech.enableVoiceMode()).called(1);
    });

    test('sets isVoiceMode to true on success', () async {
      when(mockSpeech.enableVoiceMode()).thenAnswer((_) async {});
      await vm.startChat(voiceMode: false);
      await vm.switchToVoiceMode();
      expect(vm.isVoiceMode, isTrue);
    });

    test('reverts isVoiceMode and stores error on failure', () async {
      when(mockSpeech.enableVoiceMode())
          .thenThrow(Exception('No mic permission'));
      await vm.startChat(voiceMode: false);
      await vm.switchToVoiceMode();
      expect(vm.isVoiceMode, isFalse);
      expect(vm.error, contains('Failed to switch'));
    });

    test('is no-op when already in voice mode', () async {
      when(mockSpeech.enableVoiceMode()).thenAnswer((_) async {});
      await vm.startChat(voiceMode: true);
      clearInteractions(mockSpeech);
      await vm.switchToVoiceMode();
      verifyNever(mockSpeech.enableVoiceMode());
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // stopChat() — resets new fields
  // ══════════════════════════════════════════════════════════════════════════

  group('stopChat() new-field reset', () {
    test('resets isVoiceMode and dataChannelReady', () async {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenAnswer((_) async {});
      final cbs = init();
      await vm.startChat(voiceMode: true);
      (cbs['dataChannelOpen'] as Function())();

      await vm.stopChat('Done');

      expect(vm.isVoiceMode, isFalse);
      // After stop a new call to sendTextMessage should set error (not ready)
      vm.sendTextMessage('should fail');
      expect(vm.error, isNotNull);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // clearError()
  // ══════════════════════════════════════════════════════════════════════════

  group('clearError()', () {
    test('clears the error field', () async {
      when(mockSpeech.startSpeech(mode: anyNamed('mode')))
          .thenThrow(Exception('boom'));
      await vm.startChat();
      expect(vm.error, isNotNull);
      vm.clearError();
      expect(vm.error, isNull);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // onRuntimeState — ViewModel state mapping
  // ══════════════════════════════════════════════════════════════════════════

  group('onRuntimeState callback', () {
    test('thinking → processing', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.thinking);
      expect(vm.conversationState, ConversationState.processing);
    });

    test('llmStreaming → processing', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.llmStreaming);
      expect(vm.conversationState, ConversationState.processing);
    });

    test('toolExecuting → processing', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.toolExecuting);
      expect(vm.conversationState, ConversationState.processing);
    });

    test('listening → listening', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.listening);
      expect(vm.conversationState, ConversationState.listening);
    });

    test('speaking → listening', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.speaking);
      expect(vm.conversationState, ConversationState.listening);
    });

    test('bootstrap → connecting', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.bootstrap);
      expect(vm.conversationState, ConversationState.connecting);
    });

    test('terminated → idle', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      rsCb(AgentRuntimeState.terminated);
      expect(vm.conversationState, ConversationState.idle);
    });

    test('calls notifyListeners on every runtime state change', () {
      final cbs = init();
      final rsCb = cbs['runtimeState'] as OnRuntimeStateCallback;
      int notifyCount = 0;
      vm.addListener(() => notifyCount++);
      rsCb(AgentRuntimeState.thinking);
      rsCb(AgentRuntimeState.speaking);
      expect(notifyCount, 2);
    });
  });
}
