import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart' as rtc;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

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

/// Abstract wrapper for Firestore to allow mocking in tests.
///
/// [watchServiceRequests] returns a [Stream] that emits whenever a
/// service request relevant to [userId] is created or updated in Firestore.
/// It monitors two queries in parallel:
///   - `selected_provider_user_id == userId` (incoming / provider-side)
///   - `seeker_user_id == userId`            (outgoing / seeker-side)
abstract class FirestoreWrapper {
  Stream<void> watchServiceRequests(String userId);
}

/// Production implementation backed by [FirebaseFirestore].
class FirebaseFirestoreWrapper implements FirestoreWrapper {
  final FirebaseFirestore _firestore;

  FirebaseFirestoreWrapper({FirebaseFirestore? firestore})
      : _firestore = firestore ?? _defaultInstance();

  /// Resolves the Firestore instance from the `FIRESTORE_DATABASE_NAME` env
  /// var so the app always targets the same named database as the backend.
  static FirebaseFirestore _defaultInstance() {
    final dbName = dotenv.env['FIRESTORE_DATABASE_NAME'] ?? '(default)';
    if (dbName == '(default)') return FirebaseFirestore.instance;
    return FirebaseFirestore.instanceFor(
      app: FirebaseFirestore.instance.app,
      databaseId: dbName,
    );
  }

  @override
  Stream<void> watchServiceRequests(String userId) {
    late StreamController<void> controller;
    StreamSubscription<QuerySnapshot<Map<String, dynamic>>>? providerSub;
    StreamSubscription<QuerySnapshot<Map<String, dynamic>>>? seekerSub;

    void forward(QuerySnapshot<Map<String, dynamic>> snapshot) {
      // Skip the initial local-cache snapshot and server-sync events that
      // carry no document changes. Only forward real server-pushed changes.
      if (snapshot.metadata.isFromCache) return;
      if (snapshot.docChanges.isEmpty) return;
      if (!controller.isClosed) controller.add(null);
    }

    void onError(Object error, StackTrace stack) {
      debugPrint('[FirestoreWrapper] listener error: $error');
      if (!controller.isClosed) controller.addError(error, stack);
    }

    controller = StreamController<void>(
      onListen: () {
        providerSub = _firestore
            .collection('service_requests')
            .where('selected_provider_user_id', isEqualTo: userId)
            .snapshots(includeMetadataChanges: true)
            .listen(forward, onError: onError);

        seekerSub = _firestore
            .collection('service_requests')
            .where('seeker_user_id', isEqualTo: userId)
            .snapshots(includeMetadataChanges: true)
            .listen(forward, onError: onError);
      },
      onCancel: () async {
        await providerSub?.cancel();
        await seekerSub?.cancel();
        if (!controller.isClosed) controller.close();
      },
    );

    return controller.stream;
  }
}
