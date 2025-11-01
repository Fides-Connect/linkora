import 'dart:async';
import 'dart:core';
import 'dart:typed_data';

import 'package:google_speech/google_speech.dart';
import 'package:grpc/grpc.dart' hide Codec;
import 'package:connectx/generated/cloud_tts.pbgrpc.dart' as cloud_tts;
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:record/record.dart';
import 'package:taudio/taudio.dart' as ta;

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
  ta.FlutterSoundPlayer? _player;
  final BytesBuilder _ttsBuffer = BytesBuilder(copy: false);

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

    // stop taudio player if started
    try { await _player?.stopPlayer(); } catch (_) {}
    try { await _player?.closePlayer(); } catch (_) {}
    _player = null;

    _speechToText = null;
    _textToSpeech = null;
    _clientChannel = null;
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
          // Cancel current audio synthesis and stop playback if new speech is detected
          try { _audioSynthesisSubscription?.cancel(); } catch (_) {}
          try { _player?.stopPlayer(); } catch (_) {}

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
    // Open taudio player once; we'll use fromDataBuffer for playback
    _player = ta.FlutterSoundPlayer();
    await _player!.openPlayer();
  }

  // WAV wrapper for raw PCM16 mono
  Uint8List _pcmToWav(Uint8List pcm, {required int sampleRate}) {
    const channels = 1;
    const bitsPerSample = 16;
    final byteRate = sampleRate * channels * (bitsPerSample ~/ 8);
    final blockAlign = channels * (bitsPerSample ~/ 8);
    final dataLength = pcm.lengthInBytes;
    final header = ByteData(44);
    header.setUint32(0, 0x52494646, Endian.big); // 'RIFF'
    header.setUint32(4, 36 + dataLength, Endian.little);
    header.setUint32(8, 0x57415645, Endian.big); // 'WAVE'
    header.setUint32(12, 0x666d7420, Endian.big); // 'fmt '
    header.setUint32(16, 16, Endian.little); // PCM chunk size
    header.setUint16(20, 1, Endian.little); // PCM format
    header.setUint16(22, channels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(28, byteRate, Endian.little);
    header.setUint16(32, blockAlign, Endian.little);
    header.setUint16(34, bitsPerSample, Endian.little);
    header.setUint32(36, 0x64617461, Endian.big); // 'data'
    header.setUint32(40, dataLength, Endian.little);
    final bytes = BytesBuilder(copy: false)
      ..add(header.buffer.asUint8List())
      ..add(pcm);
    return bytes.takeBytes();
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

      // reset buffer and any ongoing playback/subscription
      try { _audioSynthesisSubscription?.cancel(); } catch (_) {}
      _audioSynthesisSubscription = null;
      _ttsBuffer.clear();

      _audioSynthesisSubscription = responseStream?.listen(
        (data) {
          final audioChunk = Uint8List.fromList(data.audioContent);
          if (audioChunk.isNotEmpty) {
            _ttsBuffer.add(audioChunk);
          }
        },
        onError: (e) {
          // ignore: avoid_print
          print('Error during TTS streaming: $e');
        },
        onDone: () async {
          final pcm = _ttsBuffer.takeBytes();
          if (pcm.isEmpty) return;
          final wav = _pcmToWav(pcm, sampleRate: 16000);
          try { await _player?.stopPlayer(); } catch (_) {}
          try {
            await _player?.startPlayer(
              fromDataBuffer: wav,
              codec: ta.Codec.pcm16WAV,
            );
          } catch (e) {
            // ignore: avoid_print
            print('taudio startPlayer error: $e');
          }
        },
      );
    }
  }
}
