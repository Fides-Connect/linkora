import 'package:mockito/annotations.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:connectx/services/webrtc_service.dart';
import 'package:connectx/services/speech_service.dart';
import 'package:connectx/services/wrappers.dart';

@GenerateMocks([
  WebRTCService,
  SpeechService,
  WebSocketChannel,
  WebSocketSink,
  RTCPeerConnection,
  MediaStream,
  MediaStreamTrack,
  RTCVideoRenderer,
  RTCSessionDescription,
  RTCIceCandidate,
  RTCDataChannel,
  PermissionWrapper,
  WebRTCWrapper,
  FirebaseAuthWrapper,
  User,
  RTCRtpSender,
])
void main() {}
