import 'package:mockito/annotations.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:connectx/services/webrtc_service.dart';
import 'package:connectx/services/speech_service.dart';
import 'package:connectx/services/wrappers.dart';
import 'package:connectx/services/api_service.dart';
import 'package:connectx/services/auth_service.dart';
import 'package:connectx/features/home/data/repositories/home_repository.dart';
import 'package:http/http.dart' as http;

@GenerateNiceMocks([
  MockSpec<SpeechService>(),
])
@GenerateMocks([
  WebRTCService,
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
  ApiService,
  HomeRepository,
  AuthService,
  http.Client,
])
void main() {}
