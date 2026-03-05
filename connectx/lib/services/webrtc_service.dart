import 'dart:async';
import 'dart:convert';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'wrappers.dart';
import 'audio_routing_service.dart';
import '../models/app_types.dart';

/// WebRTC service for connecting to the AI-Assistant server
/// Handles WebSocket signaling and WebRTC peer connection
class WebRTCService {
  // WebSocket signaling
  WebSocketChannel? _signaling;

  // WebRTC components
  RTCPeerConnection? _peerConnection;
  MediaStream? _localStream;
  MediaStream? _remoteStream;

  // Audio track for sending
  MediaStreamTrack? _audioTrack;

  // Desired mute state (persisted even when track is not yet created)
  bool _desiredMuteState = true;

  // Data Channel
  RTCDataChannel? _dataChannel;

  // Audio routing service
  AudioRoutingService? _audioRoutingService;

  // Track recreation flag to prevent concurrent calls
  bool _isRecreatingTrack = false;

  // True from the moment we send a renegotiation offer until we process the
  // matching answer.  Guards _recreateAudioTrack from firing a second offer
  // while the first renegotiation round-trip is still in flight (e.g., the
  // AudioRoutingService timer detects a device change mid-renegotiation).
  bool _isRenegotiating = false;

  // Session mode ('voice' or 'text')
  String _sessionMode = 'voice';

  // Data channel open tracking (for safe pending-message flush)
  bool _dataChannelOpenFired = false;

  // Callbacks
  Function()? onConnected;
  Function()? onDisconnected;
  Function(MediaStream)? onRemoteStream;
  Function(String)? onError;
  Function(String, bool, bool)? onChatMessage; // text, isUser, isChunk
  Function()? onDataChannelOpen;
  OnRuntimeStateCallback? onRuntimeState;

  // Configuration
  late final String _serverUrl;
  bool _isConnected = false;
  bool _isConnecting = false;

  // ICE candidates queue (store candidates received before remote description is set)
  final List<RTCIceCandidate> _iceCandidatesQueue = [];
  bool _remoteDescriptionSet = false;

  // ICE server config received from backend (includes TURN credentials)
  List<Map<String, dynamic>>? _iceServers;
  Completer<void>? _iceConfigCompleter;
  final Duration _iceConfigTimeout;

  // Language configuration
  final String _languageCode;

  // Whether the server URL is secure (wss/https → Cloud Run auth required)
  bool _isSecure = false;

  // Dependencies
  final WebRTCWrapper _webRTCWrapper;
  final WebSocketChannel Function(Uri, Map<String, dynamic>) _webSocketFactory;
  final FirebaseAuthWrapper _firebaseAuthWrapper;
  final AudioRoutingService Function()? _audioRoutingServiceFactory;

  WebRTCService({
    WebRTCWrapper? webRTCWrapper,
    WebSocketChannel Function(Uri, Map<String, dynamic>)? webSocketFactory,
    FirebaseAuthWrapper? firebaseAuthWrapper,
    AudioRoutingService Function()? audioRoutingServiceFactory,
    String? serverUrl,
    String? languageCode,
    Duration iceConfigTimeout = const Duration(seconds: 5),
  }) : _webRTCWrapper = webRTCWrapper ?? WebRTCWrapper(),
       _webSocketFactory =
           webSocketFactory ??
               ((uri, headers) => kIsWeb
                   ? WebSocketChannel.connect(uri)
                   : IOWebSocketChannel.connect(uri, headers: headers)),
       _firebaseAuthWrapper = firebaseAuthWrapper ?? FirebaseAuthWrapper(),
       _audioRoutingServiceFactory = audioRoutingServiceFactory,
       _iceConfigTimeout = iceConfigTimeout,
       _languageCode = languageCode ?? 'de' {
    // Load server URL from environment variable
    final String? rawServer =
        serverUrl ?? dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      throw Exception(
        'AI_ASSISTANT_SERVER_URL not set in .env. Add AI_ASSISTANT_SERVER_URL to .env',
      );
    }
    // Detect protocol and map https→wss, http/bare→ws.
    if (rawServer.startsWith('https://')) {
      _serverUrl = rawServer.replaceFirst('https://', 'wss://') + '/ws';
      _isSecure = true;
    } else if (rawServer.startsWith('http://')) {
      _serverUrl = rawServer.replaceFirst('http://', 'ws://') + '/ws';
    } else {
      // Bare host(:port) — local development
      _serverUrl = 'ws://$rawServer/ws';
    }
  }

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;

  /// Get the audio routing service for manual control if needed
  AudioRoutingService? get audioRouting => _audioRoutingService;

  /// Check if microphone is currently muted
  /// Returns true if muted or if audio track is not initialized (default state)
  bool get isMicrophoneMuted {
    if (_audioTrack != null) {
      return !_audioTrack!.enabled;
    }
    return true;
  }

  /// Set microphone muted state
  ///
  /// Enables or disables the audio track to mute/unmute the microphone.
  /// If the audio track is not yet initialized, the desired state is stored
  /// and will be applied when the track is created.
  ///
  /// [muted] - true to mute the microphone, false to unmute
  void setMicrophoneMuted(bool muted) {
    _desiredMuteState = muted;
    if (_audioTrack != null) {
      _audioTrack!.enabled = !muted;
    } else {
      debugPrint(
        'WebRTC: Microphone ${muted ? "mute" : "unmute"} requested before track initialized - will apply when ready',
      );
    }
  }

  /// Initialize and connect to the AI-Assistant server
  Future<void> connect({String mode = 'voice'}) async {
    if (_isConnected || _isConnecting) return;

    const validModes = {'voice', 'text'};
    final String validatedMode;
    if (validModes.contains(mode)) {
      validatedMode = mode;
    } else {
      debugPrint(
        'WebRTC: Invalid session mode "$mode" provided to connect(); defaulting to "voice".',
      );
      validatedMode = 'voice';
    }

    _sessionMode = validatedMode;
    _dataChannelOpenFired = false;
    _iceConfigCompleter = Completer<void>();

    _isConnecting = true;

    try {
      // Voice mode: capture mic audio and send it to the server.
      // Text mode: receive-only — no local audio track needed.
      if (validatedMode == 'voice') {
        if (!kIsWeb) {
          _audioRoutingService =
              _audioRoutingServiceFactory?.call() ?? AudioRoutingService();
          _audioRoutingService!.onInputDeviceChanged = _recreateAudioTrack;
          await _audioRoutingService!.initialize();
        }
        await _createLocalStream();
      }

      await _connectSignaling();

      // Wait for the server to push ICE/TURN credentials before creating the
      // peer connection.  The backend sends 'ice-config' immediately on WS
      // connect; we give it up to 5 s before falling back to plain STUN.
      try {
        await _iceConfigCompleter!.future.timeout(_iceConfigTimeout);
      } on TimeoutException {
        debugPrint(
          'WebRTC: Ice-config not received in time — using default STUN',
        );
      }

      await _createPeerConnection();
      await _createOffer();
    } catch (e) {
      debugPrint('WebRTC: Connection failed: $e');
      _isConnecting = false;
      onError?.call('Connection failed: $e');
      await disconnect();
      rethrow;
    }
  }

  /// Disconnect from the AI-Assistant server
  Future<void> disconnect() async {
    _isConnected = false;
    _isConnecting = false;
    _remoteDescriptionSet = false;
    _dataChannelOpenFired = false;
    _isRenegotiating = false;
    _isRecreatingTrack = false;
    _iceCandidatesQueue.clear();
    _iceServers = null;
    if (_iceConfigCompleter != null && !_iceConfigCompleter!.isCompleted) {
      _iceConfigCompleter!.completeError('disconnected');
    }
    _iceConfigCompleter = null;

    await _signaling?.sink.close();
    _signaling = null;

    if (_localStream != null) {
      _localStream!.getTracks().forEach((track) => track.stop());
      await _localStream!.dispose();
      _localStream = null;
    }

    if (_remoteStream != null) {
      _remoteStream!.getTracks().forEach((track) => track.stop());
      await _remoteStream!.dispose();
      _remoteStream = null;
    }

    await _peerConnection?.close();
    _peerConnection = null;

    _dataChannel?.close();
    _dataChannel = null;
    _audioTrack = null;

    _audioRoutingService?.dispose();
    _audioRoutingService = null;

    onDisconnected?.call();
  }

  /// Create local audio stream from microphone
  Future<void> _createLocalStream({bool startMuted = true}) async {
    // Sync _desiredMuteState so the caller's intent is authoritative.
    // This is critical for enableVoiceMode(), which passes startMuted: false
    // but _desiredMuteState still holds its default (true) at that point.
    _desiredMuteState = startMuted;
    try {
      final Map<String, dynamic> mediaConstraints = {
        'audio': {
          'mandatory': {
            'echoCancellation': 'true',
            'noiseSuppression': 'true',
            'autoGainControl': 'true',
            'googEchoCancellation': 'true',
            'googEchoCancellation2': 'true',
            'googAutoGainControl': 'true',
            'googAutoGainControl2': 'true',
            'googNoiseSuppression': 'true',
            'googHighpassFilter': 'true',
            'googTypingNoiseDetection': 'true',
            'googDAEchoCancellation': 'true',
          },
        },
        'video': false,
      };

      _localStream = await _webRTCWrapper.getUserMedia(mediaConstraints);

      if (_localStream != null && _localStream!.getAudioTracks().isNotEmpty) {
        _audioTrack = _localStream!.getAudioTracks()[0];
        // Apply the desired mute state (use _desiredMuteState if set, otherwise use startMuted)
        _audioTrack!.enabled = !_desiredMuteState;
      } else {
        throw Exception('Failed to get audio track from local stream');
      }
    } catch (e) {
      debugPrint('WebRTC: Error creating local stream: $e');
      rethrow;
    }
  }

  /// Recreate audio track when input device changes (e.g., Bluetooth connects mid-stream)
  ///
  /// Strategy: Keep old track running until new track is ready to minimize audio gap
  Future<void> _recreateAudioTrack() async {
    if (_peerConnection == null || _localStream == null || _isRecreatingTrack ||
        _isRenegotiating) {
      // Suppress device-change renegotiations while one is already in flight.
      // AudioRoutingService will re-detect the change on its next timer tick
      // once the current renegotiation completes.
      return;
    }

    try {
      _isRecreatingTrack = true;
      final wasMuted = isMicrophoneMuted;

      // Save references to old stream/track for later disposal
      final oldStream = _localStream;
      final oldTrack = _audioTrack;

      // Create new stream FIRST, before stopping the old one
      // This minimizes the gap where no audio is being captured
      _localStream = null;
      _audioTrack = null;

      try {
        await _createLocalStream(startMuted: wasMuted);
      } catch (createError) {
        // If stream creation fails, restore the old stream/track to keep audio working
        _localStream = oldStream;
        _audioTrack = oldTrack;
        debugPrint(
          'WebRTC: Failed to create new stream, keeping old stream: $createError',
        );
        rethrow;
      }

      // Now that new track is ready, remove old track from peer connection
      if (oldTrack != null) {
        final senders = await _peerConnection!.getSenders();
        for (final sender in senders) {
          if (sender.track?.id == oldTrack.id) {
            await _peerConnection!.removeTrack(sender);
            break;
          }
        }
      }

      // Dispose old stream and its tracks after new stream is ready
      if (oldStream != null) {
        oldStream.getTracks().forEach((track) => track.stop());
        await oldStream.dispose();
      }

      if (_audioTrack != null &&
          _localStream != null &&
          _peerConnection != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);

        // Restore muted state if track was previously muted
        if (wasMuted) {
          _audioTrack!.enabled = false;
        }

        await _renegotiateConnection();
      }
    } catch (e) {
      debugPrint('WebRTC: Error recreating audio track: $e');
    } finally {
      _isRecreatingTrack = false;
    }
  }

  /// Renegotiate connection after track changes
  Future<void> _renegotiateConnection() async {
    if (_peerConnection == null) return;

    // Mark renegotiation as in-flight so _recreateAudioTrack is suppressed
    // until the answer arrives and _handleAnswer clears this flag.
    _isRenegotiating = true;
    try {
      final RTCSessionDescription offer = await _peerConnection!.createOffer({
        'offerToReceiveAudio': true,
        'offerToReceiveVideo': false,
      });

      await _peerConnection!.setLocalDescription(offer);
      _sendSignalingMessage({'type': 'offer', 'sdp': offer.sdp});
    } catch (e) {
      _isRenegotiating = false; // allow retry if offer creation itself failed
      debugPrint('WebRTC: Renegotiation error: $e');
    }
  }

  /// Connect to WebSocket signaling server
  Future<void> _connectSignaling() async {
    try {
      final User? currentUser = _firebaseAuthWrapper.currentUser;
      final String userId = currentUser?.uid ?? '';

      if (userId.isEmpty) {
        throw Exception('No authenticated user found');
      }

      // For secure (Cloud Run) connections, pass the Firebase ID token via the
      // Authorization header so it is never written to URL access logs.
      // For plain ws:// (local dev) we skip the token entirely.
      final Map<String, String> queryParams = {
        'user_id': userId,
        'language': _languageCode,
        'mode': _sessionMode,
      };

      // Non-web platforms support custom headers on the WebSocket upgrade request.
      // Always authenticate regardless of transport security (ws:// local dev or wss:// prod).
      final Map<String, dynamic> wsHeaders = {};
      if (!kIsWeb) {
        final String? idToken = await _firebaseAuthWrapper.getIdToken();
        if (idToken == null || idToken.isEmpty) {
          throw Exception('Could not retrieve Firebase ID token for authenticated request');
        }
        wsHeaders['Authorization'] = 'Bearer $idToken';
      }

      final Uri wsUri = Uri.parse(_serverUrl).replace(
        queryParameters: queryParams,
      );
      _signaling = _webSocketFactory(wsUri, wsHeaders);

      // Web browsers cannot set custom headers on WebSocket upgrade requests (browser security
      // restriction). Send the Firebase ID token as the first message so the server can
      // authenticate the web connection before processing any signaling messages.
      if (kIsWeb && _isSecure) {
        final String? idToken = await _firebaseAuthWrapper.getIdToken();
        if (idToken != null && idToken.isNotEmpty) {
          _signaling!.sink.add(json.encode({'type': 'auth', 'token': idToken}));
        }
      }

      _signaling!.stream.listen(
        _handleSignalingMessage,
        onError: (error) {
          debugPrint('WebRTC: Signaling error: $error');
          onError?.call('Signaling error: $error');
        },
        onDone: () {
          if (_isConnected || _isConnecting) disconnect();
        },
      );
    } catch (e) {
      debugPrint('WebRTC: Signaling connection error: $e');
      rethrow;
    }
  }

  /// Create WebRTC peer connection
  Future<void> _createPeerConnection() async {
    try {
      final List<Map<String, dynamic>> iceServerList = _iceServers ??
          [
            {'urls': 'stun:stun.l.google.com:19302'},
          ];

      final Map<String, dynamic> configuration = {
        'iceServers': iceServerList,
        'sdpSemantics': 'unified-plan',
      };

      _peerConnection = await _webRTCWrapper.createPeerConnection(
        configuration,
      );

      final dataChannelInit = RTCDataChannelInit()..ordered = true;
      _dataChannel = await _peerConnection!.createDataChannel(
        'chat',
        dataChannelInit,
      );

      _dataChannel!.onMessage = (RTCDataChannelMessage message) {
        if (message.isBinary) return;
        try {
          final data = jsonDecode(message.text);
          if (data['type'] == 'chat') {
            onChatMessage?.call(
              data['text'],
              data['isUser'],
              data['isChunk'] ?? false,
            );
          } else if (data['type'] == 'runtime-state') {
            final raw = data['runtimeState'] as String?;
            if (raw != null) {
              final state = AgentRuntimeState.tryParse(raw);
              if (state != null) onRuntimeState?.call(state);
            }
          }
        } catch (e) {
          debugPrint('WebRTC: Data channel message error: $e');
        }
      };

      // Primary gate: fire when the data channel explicitly opens
      _dataChannel!.onDataChannelState = (RTCDataChannelState state) {
        if (state == RTCDataChannelState.RTCDataChannelOpen &&
            !_dataChannelOpenFired) {
          _dataChannelOpenFired = true;
          onDataChannelOpen?.call();
        }
      };

      if (_audioTrack != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);
      }

      _peerConnection!.onIceCandidate = (RTCIceCandidate candidate) {
        _sendSignalingMessage({
          'type': 'ice-candidate',
          'candidate': {
            'candidate': candidate.candidate,
            'sdpMid': candidate.sdpMid,
            'sdpMLineIndex': candidate.sdpMLineIndex,
          },
        });
      };

      _peerConnection!
          .onConnectionState = (RTCPeerConnectionState state) async {
        if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
          _isConnected = true;
          _isConnecting = false;
          onConnected?.call();
          // Safety net: if data channel was already open before this callback fired
          if (_dataChannel?.state == RTCDataChannelState.RTCDataChannelOpen &&
              !_dataChannelOpenFired) {
            _dataChannelOpenFired = true;
            onDataChannelOpen?.call();
          }
        } else if (state ==
                RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
            state ==
                RTCPeerConnectionState.RTCPeerConnectionStateDisconnected ||
            state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
          if (_isConnected || _isConnecting) disconnect();
        }
      };

      _peerConnection!.onTrack = (RTCTrackEvent event) async {
        if (event.track.kind == 'audio' && _remoteStream == null) {
          _remoteStream = event.streams[0];
          onRemoteStream?.call(_remoteStream!);
        }
      };
    } catch (e) {
      debugPrint('WebRTC: Peer connection error: $e');
      rethrow;
    }
  }

  /// Create and send WebRTC offer
  Future<void> _createOffer() async {
    try {
      final RTCSessionDescription offer = await _peerConnection!.createOffer({
        'offerToReceiveAudio': true,
        'offerToReceiveVideo': false,
      });

      await _peerConnection!.setLocalDescription(offer);
      _sendSignalingMessage({'type': 'offer', 'sdp': offer.sdp});
    } catch (e) {
      debugPrint('WebRTC: Error creating offer: $e');
      rethrow;
    }
  }

  /// Handle incoming signaling messages
  void _handleSignalingMessage(dynamic message) {
    try {
      final Map<String, dynamic> data = json.decode(message);
      final String? type = data['type'];

      switch (type) {
        case 'ice-config':
          final rawServers = data['iceServers'];
          if (rawServers is List) {
            _iceServers = rawServers
                .whereType<Map<String, dynamic>>()
                .toList();
            debugPrint(
              'WebRTC: Received ${_iceServers!.length} ICE server(s) from server',
            );
          }
          if (_iceConfigCompleter != null &&
              !_iceConfigCompleter!.isCompleted) {
            _iceConfigCompleter!.complete();
          }
          break;
        case 'answer':
          _handleAnswer(data['sdp']);
          break;
        case 'ice-candidate':
          _handleIceCandidate(data['candidate']);
          break;
      }
    } catch (e) {
      debugPrint('WebRTC: Signaling message error: $e');
    }
  }

  /// Handle WebRTC answer from server
  Future<void> _handleAnswer(String sdp) async {
    try {
      final RTCSessionDescription answer = RTCSessionDescription(sdp, 'answer');
      await _peerConnection!.setRemoteDescription(answer);
      _remoteDescriptionSet = true;
      // Peer connection is now in 'stable' state — device-change renegotiations
      // are safe again.
      _isRenegotiating = false;

      if (_iceCandidatesQueue.isNotEmpty) {
        for (final candidate in _iceCandidatesQueue) {
          await _peerConnection!.addCandidate(candidate);
        }
        _iceCandidatesQueue.clear();
      }
    } catch (e) {
      // Also clear on error (e.g., "wrong state: stable" for a duplicate answer)
      // so future renegotiations are not permanently blocked.
      _isRenegotiating = false;
      debugPrint('WebRTC: Answer handling error: $e');
    }
  }

  /// Handle ICE candidate from server
  Future<void> _handleIceCandidate(Map<String, dynamic> candidateData) async {
    try {
      final RTCIceCandidate candidate = RTCIceCandidate(
        candidateData['candidate'],
        candidateData['sdpMid'],
        candidateData['sdpMLineIndex'],
      );

      if (_remoteDescriptionSet) {
        await _peerConnection!.addCandidate(candidate);
      } else {
        _iceCandidatesQueue.add(candidate);
      }
    } catch (e) {
      debugPrint('WebRTC: ICE candidate error: $e');
    }
  }

  /// Send signaling message to server
  void _sendSignalingMessage(Map<String, dynamic> message) {
    _signaling?.sink.add(json.encode(message));
  }

  /// Send text message to server via data channel
  ///
  /// This allows sending text input directly to the AI assistant,
  /// bypassing the speech-to-text step while maintaining the conversation
  ///
  /// [text] - The text message to send
  void sendTextMessage(String text) {
    if (_dataChannel != null &&
        _dataChannel!.state == RTCDataChannelState.RTCDataChannelOpen) {
      try {
        final message = jsonEncode({'type': 'text-input', 'text': text});
        _dataChannel!.send(RTCDataChannelMessage(message));
        debugPrint(
          'WebRTC: Sent text message (${text.length} chars) over data channel',
        );
      } catch (e) {
        debugPrint('WebRTC: Error sending text message: $e');
        onError?.call('Failed to send text message: $e');
      }
    } else {
      debugPrint('WebRTC: Data channel not available or not open');
      onError?.call('Cannot send message: Connection not ready');
    }
  }

  /// Send a mode-switch notification to the server over the data channel.
  ///
  /// Used to pause/resume the voice pipeline without a WebRTC renegotiation.
  /// [mode] is either 'text' or 'voice'.
  void sendModeSwitch(String mode) {
    if (_dataChannel != null &&
        _dataChannel!.state == RTCDataChannelState.RTCDataChannelOpen) {
      try {
        _dataChannel!.send(
          RTCDataChannelMessage(
            jsonEncode({'type': 'mode-switch', 'mode': mode}),
          ),
        );
        debugPrint('WebRTC: Sent mode-switch \u2192 $mode');
      } catch (e) {
        debugPrint('WebRTC: Error sending mode-switch: $e');
      }
    } else {
      debugPrint('WebRTC: Cannot send mode-switch \u2014 data channel not open');
    }
  }

  /// Upgrade a text session to voice by creating a local audio track and
  /// renegotiating the peer connection.  No-op if already in voice mode.
  Future<void> enableVoiceMode() async {
    if (!_isConnected || _peerConnection == null) {
      debugPrint('WebRTC: Cannot enable voice mode – not connected');
      return;
    }
    if (_audioTrack != null) {
      // Resuming a previously paused voice session:
      // unmute the existing track and tell the server to re-enable TTS.
      setMicrophoneMuted(false);
      sendModeSwitch('voice');
      return;
    }

    try {
      if (!kIsWeb) {
        _audioRoutingService =
            _audioRoutingServiceFactory?.call() ?? AudioRoutingService();
        _audioRoutingService!.onInputDeviceChanged = _recreateAudioTrack;
        await _audioRoutingService!.initialize();
      }
      await _createLocalStream(startMuted: false);

      if (_audioTrack != null && _localStream != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);
        await _renegotiateConnection();
      }
    } catch (e) {
      debugPrint('WebRTC: Error enabling voice mode: $e');
      rethrow;
    }
  }
}
