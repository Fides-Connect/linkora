import 'dart:async';
import 'dart:convert';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform, debugPrint;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'wrappers.dart';

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

  WebRTCService({
    WebRTCWrapper? webRTCWrapper,
    WebSocketChannel Function(Uri)? webSocketFactory,
    FirebaseAuthWrapper? firebaseAuthWrapper,
    String? serverUrl,
    String? languageCode,
  })  : _webRTCWrapper = webRTCWrapper ?? WebRTCWrapper(),
        _webSocketFactory =
            webSocketFactory ?? ((uri) => WebSocketChannel.connect(uri)),
        _firebaseAuthWrapper = firebaseAuthWrapper ?? FirebaseAuthWrapper(),
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
    if (_isConnected || _isConnecting) {
      debugPrint('WebRTC: Already connected or connecting');
      return;
    }

    _isConnecting = true;

    try {
      debugPrint('WebRTC: Connecting to $_serverUrl');

      // Create local audio stream
      await _createLocalStream();

      // Connect to signaling server
      await _connectSignaling();

      // Create peer connection
      await _createPeerConnection();

      // Create and send offer
      await _createOffer();

      debugPrint('WebRTC: Connection process initiated');
    } catch (e) {
      debugPrint('WebRTC: Error during connection: $e');
      _isConnecting = false;
      onError?.call('Connection failed: $e');
      await disconnect();
      rethrow;
    }
  }

  /// Disconnect from the AI-Assistant server
  Future<void> disconnect() async {
    debugPrint('WebRTC: Disconnecting...');

    _isConnected = false;
    _isConnecting = false;
    _remoteDescriptionSet = false;
    _iceCandidatesQueue.clear();

    // Close signaling
    await _signaling?.sink.close();
    _signaling = null;

    // Stop local stream
    if (_localStream != null) {
      _localStream!.getTracks().forEach((track) {
        track.stop();
      });
      await _localStream!.dispose();
      _localStream = null;
    }

    // Stop remote stream
    if (_remoteStream != null) {
      _remoteStream!.getTracks().forEach((track) {
        track.stop();
      });
      await _remoteStream!.dispose();
      _remoteStream = null;
    }

    // Close peer connection
    await _peerConnection?.close();
    _peerConnection = null;
    
    _dataChannel?.close();
    _dataChannel = null;

    _audioTrack = null;

    onDisconnected?.call();
    debugPrint('WebRTC: Disconnected');
  }

  /// Create local audio stream from microphone
  Future<void> _createLocalStream() async {
    debugPrint('WebRTC: Creating local audio stream');

    try {
      final Map<String, dynamic> mediaConstraints = {
        'audio': {
          'mandatory': {
            'echoCancellation': 'true',
            'noiseSuppression': 'true',
            'autoGainControl': 'true',
            // Additional Android-specific constraints (WebRTC will ignore these on other platforms)
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

      _localStream = await _webRTCWrapper.getUserMedia(
        mediaConstraints,
      );

      if (_localStream != null && _localStream!.getAudioTracks().isNotEmpty) {
        _audioTrack = _localStream!.getAudioTracks()[0];
        // Start muted by default to prevent audio leakage before connection is ready
        _audioTrack!.enabled = false;
        debugPrint('WebRTC: Local audio stream created: ${_audioTrack!.id}');
      } else {
        throw Exception('Failed to get audio track from local stream');
      }
    } catch (e) {
      debugPrint('WebRTC: Error creating local stream: $e');
      rethrow;
    }
  }

  /// Connect to WebSocket signaling server
  Future<void> _connectSignaling() async {
    debugPrint('WebRTC: Connecting to signaling server: $_serverUrl');

    try {
      // Get the current user's ID from Firebase
      final User? currentUser = _firebaseAuthWrapper.currentUser;
      final String userId = currentUser?.uid ?? '';

      if (userId.isEmpty) {
        throw Exception('No authenticated user found. Cannot connect to signaling server.');
      }

      final Uri wsUri = Uri.parse(_serverUrl).replace(queryParameters: {
        'user_id': userId,
        'language': _languageCode,
      });
      _signaling = _webSocketFactory(wsUri);

      // Listen for signaling messages
      _signaling!.stream.listen(
        (message) {
          _handleSignalingMessage(message);
        },
        onError: (error) {
          debugPrint('WebRTC: Signaling error: $error');
          onError?.call('Signaling error: $error');
        },
        onDone: () {
          debugPrint('WebRTC: Signaling connection closed');
          if (_isConnected || _isConnecting) {
            disconnect();
          }
        },
      );

      debugPrint('WebRTC: Signaling connected with user_id: $userId');
    } catch (e) {
      debugPrint('WebRTC: Error connecting to signaling server: $e');
      rethrow;
    }
  }

  /// Create WebRTC peer connection
  Future<void> _createPeerConnection() async {
    debugPrint('WebRTC: Creating peer connection');

    try {
      // ICE servers configuration
      final Map<String, dynamic> configuration = {
        'iceServers': [
          {'urls': 'stun:stun.l.google.com:19302'},
        ],
        'sdpSemantics': 'unified-plan',
      };

      _peerConnection = await _webRTCWrapper.createPeerConnection(configuration);

      // Create Data Channel
      final dataChannelInit = RTCDataChannelInit()
        ..ordered = true;
      _dataChannel = await _peerConnection!.createDataChannel('chat', dataChannelInit);
      debugPrint('WebRTC: Data channel created');

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
          debugPrint('WebRTC: Error parsing data channel message: $e');
        }
      };

      // Force earpiece mode immediately after peer connection creation
      if (!kIsWeb &&
          (defaultTargetPlatform == TargetPlatform.android ||
              defaultTargetPlatform == TargetPlatform.iOS)) {
        try {
          await Helper.setSpeakerphoneOn(false);
          debugPrint('WebRTC: Forced earpiece mode');
        } catch (e) {
          debugPrint('WebRTC: Could not force earpiece: $e');
        }
      }

      // Add local audio track to peer connection
      if (_audioTrack != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);
        debugPrint('WebRTC: Added local audio track to peer connection');
      }

      // Handle ICE candidates
      _peerConnection!.onIceCandidate = (RTCIceCandidate candidate) {
        debugPrint('WebRTC: ICE candidate generated: ${candidate.candidate}');
        _sendSignalingMessage({
          'type': 'ice-candidate',
          'candidate': {
            'candidate': candidate.candidate,
            'sdpMid': candidate.sdpMid,
            'sdpMLineIndex': candidate.sdpMLineIndex,
          },
        });
      };

      // Handle connection state changes
      _peerConnection!
          .onConnectionState = (RTCPeerConnectionState state) async {
        debugPrint('WebRTC: Connection state: $state');

        if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
          _isConnected = true;
          _isConnecting = false;

          // Re-enforce earpiece when connection is fully established
          if (!kIsWeb &&
              (defaultTargetPlatform == TargetPlatform.android ||
                  defaultTargetPlatform == TargetPlatform.iOS)) {
            try {
              await Helper.setSpeakerphoneOn(false);
              debugPrint(
                'WebRTC: Re-enforced earpiece after connection established',
              );
            } catch (e) {
              debugPrint('WebRTC: Could not re-enforce earpiece: $e');
            }
          }

          onConnected?.call();
        } else if (state ==
                RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
            state ==
                RTCPeerConnectionState.RTCPeerConnectionStateDisconnected ||
            state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
          if (_isConnected || _isConnecting) {
            disconnect();
          }
        }
      };

      // Handle remote stream
      _peerConnection!.onTrack = (RTCTrackEvent event) async {
        debugPrint('WebRTC: Received remote track: ${event.track.kind}');

        if (event.track.kind == 'audio') {
          if (_remoteStream == null) {
            _remoteStream = event.streams[0];
            onRemoteStream?.call(_remoteStream!);
            debugPrint('WebRTC: Remote audio stream received');

            // Re-enforce earpiece when remote audio arrives
            if (!kIsWeb &&
                (defaultTargetPlatform == TargetPlatform.android ||
                    defaultTargetPlatform == TargetPlatform.iOS)) {
              try {
                await Helper.setSpeakerphoneOn(false);
                debugPrint(
                  'WebRTC: Re-enforced earpiece after remote track received',
                );
              } catch (e) {
                debugPrint('WebRTC: Could not re-enforce earpiece: $e');
              }
            }
          }
        }
      };

      debugPrint('WebRTC: Peer connection created');
    } catch (e) {
      debugPrint('WebRTC: Error creating peer connection: $e');
      rethrow;
    }
  }

  /// Create and send WebRTC offer
  Future<void> _createOffer() async {
    debugPrint('WebRTC: Creating offer');

    try {
      final RTCSessionDescription offer = await _peerConnection!.createOffer({
        'offerToReceiveAudio': true,
        'offerToReceiveVideo': false,
      });

      await _peerConnection!.setLocalDescription(offer);
      debugPrint('WebRTC: Local description set (offer)');

      // Send offer to server
      _sendSignalingMessage({'type': 'offer', 'sdp': offer.sdp});

      debugPrint('WebRTC: Offer sent to server');
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

      debugPrint('WebRTC: Received signaling message: $type');

      switch (type) {
        case 'answer':
          _handleAnswer(data['sdp']);
          break;

        case 'ice-candidate':
          _handleIceCandidate(data['candidate']);
          break;

        default:
          debugPrint('WebRTC: Unknown signaling message type: $type');
      }
    } catch (e) {
      debugPrint('WebRTC: Error handling signaling message: $e');
    }
  }

  /// Handle WebRTC answer from server
  Future<void> _handleAnswer(String sdp) async {
    debugPrint('WebRTC: Handling answer from server');

    try {
      final RTCSessionDescription answer = RTCSessionDescription(sdp, 'answer');
      await _peerConnection!.setRemoteDescription(answer);
      debugPrint('WebRTC: Remote description set (answer)');

      _remoteDescriptionSet = true;

      // Process queued ICE candidates
      if (_iceCandidatesQueue.isNotEmpty) {
        debugPrint(
          'WebRTC: Processing ${_iceCandidatesQueue.length} queued ICE candidates',
        );
        for (final candidate in _iceCandidatesQueue) {
          await _peerConnection!.addCandidate(candidate);
        }
        _iceCandidatesQueue.clear();
      }
    } catch (e) {
      debugPrint('WebRTC: Error handling answer: $e');
    }
  }

  /// Handle ICE candidate from server
  Future<void> _handleIceCandidate(Map<String, dynamic> candidateData) async {
    debugPrint('WebRTC: Handling ICE candidate from server');

    try {
      final RTCIceCandidate candidate = RTCIceCandidate(
        candidateData['candidate'],
        candidateData['sdpMid'],
        candidateData['sdpMLineIndex'],
      );

      if (_remoteDescriptionSet) {
        await _peerConnection!.addCandidate(candidate);
        debugPrint('WebRTC: ICE candidate added');
      } else {
        debugPrint(
          'WebRTC: Queueing ICE candidate (remote description not set yet)',
        );
        _iceCandidatesQueue.add(candidate);
      }
    } catch (e) {
      debugPrint('WebRTC: Error handling ICE candidate: $e');
    }
  }

  /// Send signaling message to server
  void _sendSignalingMessage(Map<String, dynamic> message) {
    if (_signaling != null) {
      _signaling!.sink.add(json.encode(message));
      debugPrint('WebRTC: Sent signaling message: ${message['type']}');
    } else {
      debugPrint('WebRTC: Cannot send message, signaling is null');
    }
  }
}
