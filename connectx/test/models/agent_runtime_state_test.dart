import 'package:flutter_test/flutter_test.dart';
import 'package:connectx/models/app_types.dart';

void main() {
  group('AgentRuntimeState.tryParse', () {
    test('parses all known backend strings', () {
      final cases = {
        'bootstrap': AgentRuntimeState.bootstrap,
        'data_channel_wait': AgentRuntimeState.dataChannelWait,
        'listening': AgentRuntimeState.listening,
        'thinking': AgentRuntimeState.thinking,
        'llm_streaming': AgentRuntimeState.llmStreaming,
        'tool_executing': AgentRuntimeState.toolExecuting,
        'speaking': AgentRuntimeState.speaking,
        'interrupting': AgentRuntimeState.interrupting,
        'mode_switch': AgentRuntimeState.modeSwitch,
        'error_retryable': AgentRuntimeState.errorRetryable,
        'terminated': AgentRuntimeState.terminated,
      };

      for (final entry in cases.entries) {
        expect(
          AgentRuntimeState.tryParse(entry.key),
          entry.value,
          reason: 'tryParse("${entry.key}") should return ${entry.value}',
        );
      }
    });

    test('returns null for unknown values', () {
      expect(AgentRuntimeState.tryParse('unknown_state'), isNull);
      expect(AgentRuntimeState.tryParse(''), isNull);
      expect(AgentRuntimeState.tryParse('LISTENING'), isNull); // case-sensitive
    });
  });
}
