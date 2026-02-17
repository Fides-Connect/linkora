import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart' as rtc;
import 'package:firebase_auth/firebase_auth.dart';

/// Wrapper for Permission handler to allow mocking
class PermissionWrapper {
  Future<PermissionStatus> requestMicrophone() {
    return Permission.microphone.request();
  }
}

/// Wrapper for WebRTC global functions to allow mocking
class WebRTCWrapper {
  Future<rtc.MediaStream> getUserMedia(Map<String, dynamic> mediaConstraints) {
    return rtc.navigator.mediaDevices.getUserMedia(mediaConstraints);
  }

  Future<rtc.RTCPeerConnection> createPeerConnection(
      Map<String, dynamic> configuration,
      [Map<String, dynamic>? constraints]) async {
    return await rtc.createPeerConnection(configuration, constraints ?? {});
  }
}

/// Wrapper for FirebaseAuth to allow mocking
class FirebaseAuthWrapper {
  User? get currentUser => FirebaseAuth.instance.currentUser;
}

