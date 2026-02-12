import 'dart:async';
import 'dart:convert';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'wrappers.dart';
import 'audio_routing_service.dart';

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
  
  // Data Channel
  RTCDataChannel? _dataChannel;

  // Audio routing service
  AudioRoutingService? _audioRoutingService;
  
  // Track recreation flag to prevent concurrent calls
  bool _isRecreatingTrack = false;

  // Callbacks
  Function()? onConnected;
  Function()? onDisconnected;
  Function(MediaStream)? onRemoteStream;
  Function(String)? onError;
  Function(String, bool, bool)? onChatMessage; // text, isUser, isChunk

  // Configuration
  late final String _serverUrl;
  bool _isConnected = false;
  bool _isConnecting = false;

  // ICE candidates queue (store candidates received before remote description is set)
  final List<RTCIceCandidate> _iceCandidatesQueue = [];
  bool _remoteDescriptionSet = false;

  // Language configuration
  String _languageCode = 'de'; // Default to German

  // Dependencies
  final WebRTCWrapper _webRTCWrapper;
  final WebSocketChannel Function(Uri) _webSocketFactory;
  final FirebaseAuthWrapper _firebaseAuthWrapper;
  final AudioRoutingService Function()? _audioRoutingServiceFactory;

  WebRTCService({
    WebRTCWrapper? webRTCWrapper,
    WebSocketChannel Function(Uri)? webSocketFactory,
    FirebaseAuthWrapper? firebaseAuthWrapper,
    AudioRoutingService Function()? audioRoutingServiceFactory,
    String? serverUrl,
    String? languageCode,
  })  : _webRTCWrapper = webRTCWrapper ?? WebRTCWrapper(),
        _webSocketFactory =
            webSocketFactory ?? ((uri) => WebSocketChannel.connect(uri)),
        _firebaseAuthWrapper = firebaseAuthWrapper ?? FirebaseAuthWrapper(),
        _audioRoutingServiceFactory = audioRoutingServiceFactory,
        _languageCode = languageCode ?? 'de' {
    // Load server URL from environment variable
    final String? rawServer = serverUrl ?? dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      throw Exception(
        'AI_ASSISTANT_SERVER_URL not set in .env. Add AI_ASSISTANT_SERVER_URL to .env',
      );
    }
    _serverUrl = 'ws://$rawServer/ws';
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
  
  void setMicrophoneMuted(bool muted) {
    if (_audioTrack != null) {
      _audioTrack!.enabled = !muted;
      debugPrint('WebRTC: Microphone muted: $muted');
    } else {
      debugPrint(
          'WebRTC: Cannot set microphone muted to $muted, audio track is not initialized');
    }
  }

  /// Initialize and connect to the AI-Assistant server
  Future<void> connect() async {
    if (_isConnected || _isConnecting) return;

    _isConnecting = true;

    try {
      // Initialize audio routing service if not on web
      if (!kIsWeb) {
        _audioRoutingService = _audioRoutingServiceFactory?.call() ?? AudioRoutingService();
        _audioRoutingService!.onInputDeviceChanged = _recreateAudioTrack;
        await _audioRoutingService!.initialize();
      }

      await _createLocalStream();
      await _connectSignaling();
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
    _iceCandidatesQueue.clear();

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
        _audioTrack!.enabled = !startMuted;
      } else {
        throw Exception('Failed to get audio track from local stream');
      }
    } catch (e) {
      debugPrint('WebRTC: Error creating local stream: $e');
      rethrow;
    }
  }

  /// Recreate audio track when input device changes (e.g., Bluetooth connects mid-stream)
  Future<void> _recreateAudioTrack() async {
    if (_peerConnection == null || _localStream == null || _isRecreatingTrack) {
      return;
    }

    try {
      _isRecreatingTrack = true;
      final wasMuted = isMicrophoneMuted;
      
      // Remove old audio track
      if (_audioTrack != null) {
        final senders = await _peerConnection!.getSenders();
        for (final sender in senders) {
          if (sender.track?.id == _audioTrack!.id) {
            await _peerConnection!.removeTrack(sender);
            break;
          }
        }
        _audioTrack!.stop();
        await _audioTrack!.dispose();
      }
      
      if (_localStream != null) {
        _localStream!.getTracks().forEach((track) => track.stop());
        await _localStream!.dispose();
      }
      
      await Future.delayed(Duration(milliseconds: 200));
      await _createLocalStream(startMuted: wasMuted);
      
      if (_audioTrack != null && _peerConnection != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);
        
        // Restore muted state if track was previously muted
        if (wasMuted) {
          _audioTrack!.enabled = false;
        }
        
        await _renegotiateConnection();
      }
      
      debugPrint('WebRTC: Audio track recreated for device change');
    } catch (e) {
      debugPrint('WebRTC: Error recreating audio track: $e');
    } finally {
      _isRecreatingTrack = false;
    }
  }

  /// Renegotiate connection after track changes
  Future<void> _renegotiateConnection() async {
    if (_peerConnection == null) return;

    try {
      final RTCSessionDescription offer = await _peerConnection!.createOffer({
        'offerToReceiveAudio': true,
        'offerToReceiveVideo': false,
      });

      await _peerConnection!.setLocalDescription(offer);
      _sendSignalingMessage({'type': 'offer', 'sdp': offer.sdp});
      await Future.delayed(Duration(milliseconds: 500));
    } catch (e) {
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

      final Uri wsUri = Uri.parse(_serverUrl).replace(queryParameters: {
        'user_id': userId,
        'language': _languageCode,
      });
      _signaling = _webSocketFactory(wsUri);

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
      final Map<String, dynamic> configuration = {
        'iceServers': [
          {'urls': 'stun:stun.l.google.com:19302'},
        ],
        'sdpSemantics': 'unified-plan',
      };

      _peerConnection = await _webRTCWrapper.createPeerConnection(configuration);

      final dataChannelInit = RTCDataChannelInit()..ordered = true;
      _dataChannel = await _peerConnection!.createDataChannel('chat', dataChannelInit);

      _dataChannel!.onMessage = (RTCDataChannelMessage message) {
        if (message.isBinary) return;
        try {
          final data = jsonDecode(message.text);
          if (data['type'] == 'chat') {
            onChatMessage?.call(
              data['text'], 
              data['isUser'], 
              data['isChunk'] ?? false
            );
          }
        } catch (e) {
          debugPrint('WebRTC: Data channel message error: $e');
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

      _peerConnection!.onConnectionState = (RTCPeerConnectionState state) async {
        if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
          _isConnected = true;
          _isConnecting = false;
          onConnected?.call();
        } else if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
            state == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected ||
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

      if (_iceCandidatesQueue.isNotEmpty) {
        for (final candidate in _iceCandidatesQueue) {
          await _peerConnection!.addCandidate(candidate);
        }
        _iceCandidatesQueue.clear();
      }
    } catch (e) {
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
}
