import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

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
  final String _serverUrl;
  bool _isConnected = false;
  bool _isConnecting = false;
  
  // ICE candidates queue (store candidates received before remote description is set)
  final List<RTCIceCandidate> _iceCandidatesQueue = [];
  bool _remoteDescriptionSet = false;
  
  WebRTCService({String? serverUrl})
      : _serverUrl = serverUrl ?? dotenv.env['AI_ASSISTANT_SERVER_URL'] ?? 'ws://localhost:8080/ws';

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;
  
  /// Initialize and connect to the AI-Assistant server
  Future<void> connect() async {
    if (_isConnected || _isConnecting) {
      print('WebRTC: Already connected or connecting');
      return;
    }
    
    _isConnecting = true;
    
    try {
      print('WebRTC: Connecting to $_serverUrl');
      
      // Create local audio stream
      await _createLocalStream();
      
      // Connect to signaling server
      await _connectSignaling();
      
      // Create peer connection
      await _createPeerConnection();
      
      // Create and send offer
      await _createOffer();
      
      print('WebRTC: Connection process initiated');
      
    } catch (e) {
      print('WebRTC: Error during connection: $e');
      _isConnecting = false;
      onError?.call('Connection failed: $e');
      await disconnect();
      rethrow;
    }
  }
  
  /// Disconnect from the AI-Assistant server
  Future<void> disconnect() async {
    print('WebRTC: Disconnecting...');
    
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
    
    _audioTrack = null;
    
    onDisconnected?.call();
    print('WebRTC: Disconnected');
  }
  
  /// Create local audio stream from microphone
  Future<void> _createLocalStream() async {
    print('WebRTC: Creating local audio stream');
    
    try {
      final Map<String, dynamic> mediaConstraints = {
        'audio': {
          'echoCancellation': true,
          'noiseSuppression': true,
          'autoGainControl': true,
          'sampleRate': 48000,
          'channelCount': 1,
          // Android-specific constraints
          'googEchoCancellation': true,
          'googAutoGainControl': true,
          'googNoiseSuppression': true,
          'googHighpassFilter': true,
          'googTypingNoiseDetection': true,
          'googEchoCancellation2': true,
          'googAutoGainControl2': true,
        },
        'video': false,
      };
      
      _localStream = await navigator.mediaDevices.getUserMedia(mediaConstraints);
      
      if (_localStream != null && _localStream!.getAudioTracks().isNotEmpty) {
        _audioTrack = _localStream!.getAudioTracks()[0];
        print('WebRTC: Local audio stream created: ${_audioTrack!.id}');
      } else {
        throw Exception('Failed to get audio track from local stream');
      }
    } catch (e) {
      print('WebRTC: Error creating local stream: $e');
      rethrow;
    }
  }
  
  /// Connect to WebSocket signaling server
  Future<void> _connectSignaling() async {
    print('WebRTC: Connecting to signaling server: $_serverUrl');
    
    try {
      _signaling = WebSocketChannel.connect(Uri.parse(_serverUrl));
      
      // Listen for signaling messages
      _signaling!.stream.listen(
        (message) {
          _handleSignalingMessage(message);
        },
        onError: (error) {
          print('WebRTC: Signaling error: $error');
          onError?.call('Signaling error: $error');
        },
        onDone: () {
          print('WebRTC: Signaling connection closed');
          if (_isConnected || _isConnecting) {
            disconnect();
          }
        },
      );
      
      print('WebRTC: Signaling connected');
    } catch (e) {
      print('WebRTC: Error connecting to signaling server: $e');
      rethrow;
    }
  }
  
  /// Create WebRTC peer connection
  Future<void> _createPeerConnection() async {
    print('WebRTC: Creating peer connection');
    
    try {
      // ICE servers configuration
      final Map<String, dynamic> configuration = {
        'iceServers': [
          {'urls': 'stun:stun.l.google.com:19302'},
        ],
        'sdpSemantics': 'unified-plan',
      };
      
      _peerConnection = await createPeerConnection(configuration);
      
      // Force earpiece mode immediately after peer connection creation
      if (!kIsWeb && (defaultTargetPlatform == TargetPlatform.android || 
                      defaultTargetPlatform == TargetPlatform.iOS)) {
        try {
          await Helper.setSpeakerphoneOn(false);
          print('WebRTC: Forced earpiece mode');
        } catch (e) {
          print('WebRTC: Could not force earpiece: $e');
        }
      }
      
      // Add local audio track to peer connection
      if (_audioTrack != null) {
        await _peerConnection!.addTrack(_audioTrack!, _localStream!);
        print('WebRTC: Added local audio track to peer connection');
      }
      
      // Handle ICE candidates
      _peerConnection!.onIceCandidate = (RTCIceCandidate candidate) {
        print('WebRTC: ICE candidate generated: ${candidate.candidate}');
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
      _peerConnection!.onConnectionState = (RTCPeerConnectionState state) async {
        print('WebRTC: Connection state: $state');
        
        if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
          _isConnected = true;
          _isConnecting = false;
          
          // Re-enforce earpiece when connection is fully established
          if (!kIsWeb && (defaultTargetPlatform == TargetPlatform.android || 
                          defaultTargetPlatform == TargetPlatform.iOS)) {
            try {
              await Helper.setSpeakerphoneOn(false);
              print('WebRTC: Re-enforced earpiece after connection established');
            } catch (e) {
              print('WebRTC: Could not re-enforce earpiece: $e');
            }
          }
          
          onConnected?.call();
        } else if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
                   state == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected ||
                   state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
          if (_isConnected || _isConnecting) {
            disconnect();
          }
        }
      };
      
      // Handle remote stream
      _peerConnection!.onTrack = (RTCTrackEvent event) async {
        print('WebRTC: Received remote track: ${event.track.kind}');
        
        if (event.track.kind == 'audio') {
          if (_remoteStream == null) {
            _remoteStream = event.streams[0];
            onRemoteStream?.call(_remoteStream!);
            print('WebRTC: Remote audio stream received');
            
            // Re-enforce earpiece when remote audio arrives
            if (!kIsWeb && (defaultTargetPlatform == TargetPlatform.android || 
                            defaultTargetPlatform == TargetPlatform.iOS)) {
              try {
                await Helper.setSpeakerphoneOn(false);
                print('WebRTC: Re-enforced earpiece after remote track received');
              } catch (e) {
                print('WebRTC: Could not re-enforce earpiece: $e');
              }
            }
          }
        }
      };
      
      print('WebRTC: Peer connection created');
    } catch (e) {
      print('WebRTC: Error creating peer connection: $e');
      rethrow;
    }
  }
  
  /// Create and send WebRTC offer
  Future<void> _createOffer() async {
    print('WebRTC: Creating offer');
    
    try {
      final RTCSessionDescription offer = await _peerConnection!.createOffer({
        'offerToReceiveAudio': true,
        'offerToReceiveVideo': false,
      });
      
      await _peerConnection!.setLocalDescription(offer);
      print('WebRTC: Local description set (offer)');
      
      // Send offer to server
      _sendSignalingMessage({
        'type': 'offer',
        'sdp': offer.sdp,
      });
      
      print('WebRTC: Offer sent to server');
    } catch (e) {
      print('WebRTC: Error creating offer: $e');
      rethrow;
    }
  }
  
  /// Handle incoming signaling messages
  void _handleSignalingMessage(dynamic message) {
    try {
      final Map<String, dynamic> data = json.decode(message);
      final String? type = data['type'];
      
      print('WebRTC: Received signaling message: $type');
      
      switch (type) {
        case 'answer':
          _handleAnswer(data['sdp']);
          break;
          
        case 'ice-candidate':
          _handleIceCandidate(data['candidate']);
          break;
          
        default:
          print('WebRTC: Unknown signaling message type: $type');
      }
    } catch (e) {
      print('WebRTC: Error handling signaling message: $e');
    }
  }
  
  /// Handle WebRTC answer from server
  Future<void> _handleAnswer(String sdp) async {
    print('WebRTC: Handling answer from server');
    
    try {
      final RTCSessionDescription answer = RTCSessionDescription(sdp, 'answer');
      await _peerConnection!.setRemoteDescription(answer);
      print('WebRTC: Remote description set (answer)');
      
      _remoteDescriptionSet = true;
      
      // Process queued ICE candidates
      if (_iceCandidatesQueue.isNotEmpty) {
        print('WebRTC: Processing ${_iceCandidatesQueue.length} queued ICE candidates');
        for (final candidate in _iceCandidatesQueue) {
          await _peerConnection!.addCandidate(candidate);
        }
        _iceCandidatesQueue.clear();
      }
    } catch (e) {
      print('WebRTC: Error handling answer: $e');
    }
  }
  
  /// Handle ICE candidate from server
  Future<void> _handleIceCandidate(Map<String, dynamic> candidateData) async {
    print('WebRTC: Handling ICE candidate from server');
    
    try {
      final RTCIceCandidate candidate = RTCIceCandidate(
        candidateData['candidate'],
        candidateData['sdpMid'],
        candidateData['sdpMLineIndex'],
      );
      
      if (_remoteDescriptionSet) {
        await _peerConnection!.addCandidate(candidate);
        print('WebRTC: ICE candidate added');
      } else {
        print('WebRTC: Queueing ICE candidate (remote description not set yet)');
        _iceCandidatesQueue.add(candidate);
      }
    } catch (e) {
      print('WebRTC: Error handling ICE candidate: $e');
    }
  }
  
  /// Send signaling message to server
  void _sendSignalingMessage(Map<String, dynamic> message) {
    if (_signaling != null) {
      _signaling!.sink.add(json.encode(message));
      print('WebRTC: Sent signaling message: ${message['type']}');
    } else {
      print('WebRTC: Cannot send message, signaling is null');
    }
  }
}
