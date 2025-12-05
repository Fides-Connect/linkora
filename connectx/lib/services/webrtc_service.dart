import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform, debugPrint;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:firebase_auth/firebase_auth.dart';

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

  // Callbacks
  Function()? onConnected;
  Function()? onDisconnected;
  Function(MediaStream)? onRemoteStream;
  Function(String)? onError;

  // Configuration
  late final String _baseServerUrl;
  bool _isConnected = false;
  bool _isConnecting = false;
  bool _shouldReconnect = true;
  int _reconnectAttempts = 0;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  // ignore: unused_field
  DateTime? _lastPingReceived;  // Track last ping for monitoring/debugging

  // ICE candidates queue (store candidates received before remote description is set)
  final List<RTCIceCandidate> _iceCandidatesQueue = [];
  bool _remoteDescriptionSet = false;

  WebRTCService() {
    // Load server URL from environment variable
    final String? rawServer = dotenv.env['AI_ASSISTANT_SERVER_URL'];
    if (rawServer == null || rawServer.isEmpty) {
      throw Exception(
        'AI_ASSISTANT_SERVER_URL not set in .env. Add AI_ASSISTANT_SERVER_URL to .env',
      );
    }
    _baseServerUrl = rawServer;
  }

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;

  /// Initialize and connect to the AI-Assistant server
  Future<void> connect() async {
    if (_isConnected || _isConnecting) {
      debugPrint('WebRTC: Already connected or connecting');
      return;
    }

    _isConnecting = true;
    _shouldReconnect = true;
    _reconnectAttempts = 0;

    try {
      // Get current user for authenticated connection
      final user = FirebaseAuth.instance.currentUser;
      final userId = user?.uid;
      
      final serverUrl = userId != null 
          ? 'ws://$_baseServerUrl/ws?user_id=$userId'
          : 'ws://$_baseServerUrl/ws';
      
      debugPrint('WebRTC: Connecting to $serverUrl');

      // Create local audio stream
      await _createLocalStream();

      // Connect to signaling server
      await _connectSignaling(serverUrl);

      // Create peer connection
      await _createPeerConnection();

      // Create and send offer
      await _createOffer();

      debugPrint('WebRTC: Connection process initiated');
    } catch (e) {
      debugPrint('WebRTC: Error during connection: $e');
      _isConnecting = false;
      onError?.call('Connection failed: $e');
      
      // Try to reconnect (don't rethrow to avoid unhandled exception)
      _scheduleReconnect();
    }
  }

  /// Schedule reconnection attempt
  void _scheduleReconnect() {
    if (!_shouldReconnect) {
      debugPrint('WebRTC: Reconnection disabled, not scheduling');
      return;
    }

    _reconnectTimer?.cancel();
    
    // Exponential backoff: 2s, 4s, 8s, 16s, max 30s
    final delay = (2 << _reconnectAttempts.clamp(0, 4)).clamp(2, 30);
    _reconnectAttempts++;
    
    debugPrint('WebRTC: Scheduling reconnect attempt ${_reconnectAttempts} in ${delay}s');
    
    _reconnectTimer = Timer(Duration(seconds: delay), () async {
      debugPrint('WebRTC: Attempting reconnection...');
      try {
        await connect();
      } catch (e) {
        debugPrint('WebRTC: Reconnection attempt failed: $e');
      }
    });
  }

  /// Permanently disable reconnection (e.g., on explicit logout)
  void disableReconnection() {
    _shouldReconnect = false;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
  }

  /// Disconnect from the AI-Assistant server
  Future<void> disconnect() async {
    debugPrint('WebRTC: Disconnecting...');

    _isConnected = false;
    _isConnecting = false;
    
    // Cancel timers
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _pingTimer?.cancel();
    _pingTimer = null;
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
          // Echo cancellation - critical for preventing feedback loops
          // WebRTC uses the audio output as reference signal to cancel echo
          'echoCancellation': true,
          'noiseSuppression': true,
          'autoGainControl': true,
          'sampleRate': 48000,
          'channelCount': 1,
          
          // Android-specific echo cancellation enhancements
          // These work best when audio routing is NOT manually controlled
          'googEchoCancellation': true,
          'googAutoGainControl': true,
          'googNoiseSuppression': true,
          'googHighpassFilter': true,
          'googTypingNoiseDetection': true,
          'googEchoCancellation2': true,  // Enhanced echo cancellation
          'googAutoGainControl2': true,
        },
        'video': false,
      };

      _localStream = await navigator.mediaDevices.getUserMedia(
        mediaConstraints,
      );

      if (_localStream != null && _localStream!.getAudioTracks().isNotEmpty) {
        _audioTrack = _localStream!.getAudioTracks()[0];
        // Ensure audio track is enabled
        _audioTrack!.enabled = true;
        debugPrint('WebRTC: Local audio stream created: ${_audioTrack!.id}, enabled: ${_audioTrack!.enabled}');
      } else {
        throw Exception('Failed to get audio track from local stream');
      }
    } catch (e) {
      debugPrint('WebRTC: Error creating local stream: $e');
      rethrow;
    }
  }

  /// Connect to WebSocket signaling server
  Future<void> _connectSignaling(String serverUrl) async {
    debugPrint('WebRTC: Connecting to signaling server: $serverUrl');

    try {
      _signaling = WebSocketChannel.connect(Uri.parse(serverUrl));

      // Listen for signaling messages
      _signaling!.stream.listen(
        (message) {
          _handleSignalingMessage(message);
        },
        onError: (error) {
          debugPrint('WebRTC: Signaling error: $error');
          onError?.call('Signaling error: $error');
          _scheduleReconnect();
        },
        onDone: () {
          debugPrint('WebRTC: Signaling connection closed');
          if (_isConnected || _isConnecting) {
            final wasConnected = _isConnected;
            disconnect();
            
            // Only trigger reconnect if we should and were previously connected
            if (_shouldReconnect && wasConnected) {
              _scheduleReconnect();
            }
          }
        },
      );

      debugPrint('WebRTC: Signaling connected');
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

      _peerConnection = await createPeerConnection(configuration);

      // Add local audio track to peer connection FIRST
      if (_audioTrack != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);
        debugPrint('WebRTC: Added local audio track to peer connection (enabled: ${_audioTrack!.enabled})');
      }

      // AFTER adding track, configure audio routing for echo cancellation
      // This ensures microphone is active and echo cancellation can set up properly
      if (!kIsWeb &&
          (defaultTargetPlatform == TargetPlatform.android ||
              defaultTargetPlatform == TargetPlatform.iOS)) {
        try {
          // Use speakerphone mode (true) for testing with emulator
          // Use earpiece mode (false) for production on real device
          // TODO: Make this configurable based on environment
          await Helper.setSpeakerphoneOn(false);  // Changed to true for emulator testing
          debugPrint('WebRTC: Configured audio routing (speakerphone mode)');
        } catch (e) {
          debugPrint('WebRTC: Could not configure audio routing: $e');
        }
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
          _reconnectAttempts = 0;  // Reset reconnect attempts on success

          debugPrint('WebRTC: Connection established with automatic audio routing');

          onConnected?.call();
        } else if (state ==
                RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
            state ==
                RTCPeerConnectionState.RTCPeerConnectionStateDisconnected ||
            state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
          if (_isConnected || _isConnecting) {
            final wasConnected = _isConnected;
            disconnect();
            
            // Schedule reconnect if we were connected and should reconnect
            if (_shouldReconnect && wasConnected) {
              _scheduleReconnect();
            }
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
            
            // Audio routing is handled automatically by WebRTC for proper echo cancellation
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

        case 'ping':
          _handlePing(data);
          break;

        default:
          debugPrint('WebRTC: Unknown signaling message type: $type');
      }
    } catch (e) {
      debugPrint('WebRTC: Error handling signaling message: $e');
    }
  }

  /// Handle ping from server and respond with pong
  void _handlePing(Map<String, dynamic> data) {
    _lastPingReceived = DateTime.now();
    debugPrint('WebRTC: Received ping from server');
    
    // Respond with pong
    _sendSignalingMessage({
      'type': 'pong',
      'timestamp': data['timestamp'],
    });
    
    debugPrint('WebRTC: Sent pong to server');
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
