import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Priority levels for notifications
enum NotificationPriority {
  high,
  defaultPriority,
  low,
}

/// Service to handle local notifications using native OS mechanisms
/// Works with both iOS and Android notification systems
class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;

  /// Initialize the notification service with platform-specific settings
  Future<void> initialize() async {
    if (_isInitialized) return;

    // Android initialization settings
    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    // iOS initialization settings
    const DarwinInitializationSettings iosSettings =
        DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    // Combined initialization settings
    const InitializationSettings initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    // Initialize the plugin
    final bool? result = await _notificationsPlugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    _isInitialized = result ?? false;
    
    if (_isInitialized) {
      debugPrint('NotificationService: Initialized successfully');
    } else {
      debugPrint('NotificationService: Failed to initialize');
    }
  }

  /// Request notification permissions (primarily for iOS)
  Future<bool> requestPermissions() async {
    if (!_isInitialized) {
      await initialize();
    }

    // iOS permission request
    final bool? iosGranted = await _notificationsPlugin
        .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>()
        ?.requestPermissions(
          alert: true,
          badge: true,
          sound: true,
        );

    // Android 13+ permission request
    final bool? androidGranted = await _notificationsPlugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();

    final granted = iosGranted ?? androidGranted ?? true;
    debugPrint('NotificationService: Permissions granted: $granted');
    return granted;
  }

  /// Show a simple notification
  Future<void> showNotification({
    required int id,
    required String title,
    required String body,
    String? payload,
  }) async {
    if (!_isInitialized) {
      await initialize();
    }

    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'connectx_channel',
      'ConnectX Notifications',
      channelDescription: 'Notifications from ConnectX AI Assistant',
      importance: Importance.high,
      priority: Priority.high,
      showWhen: true,
    );

    const DarwinNotificationDetails iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    const NotificationDetails notificationDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _notificationsPlugin.show(
      id,
      title,
      body,
      notificationDetails,
      payload: payload,
    );

    debugPrint('NotificationService: Showed notification - $title');
  }

  /// Show notification for AI response
  /// 
  /// Displays a notification when the AI Assistant provides a response.
  /// Useful for showing AI replies when the app is in the background or minimized.
  /// 
  /// [message] - The AI response text to display in the notification body
  /// [customTitle] - Optional custom title, defaults to 'AI Assistant'
  /// [priority] - Optional priority level (high, default, low), defaults to high
  /// [showTimestamp] - Whether to show the timestamp, defaults to true
  /// 
  /// Example:
  /// ```dart
  /// await notificationService.showAIResponseNotification(
  ///   'Hello! How can I help you today?',
  ///   customTitle: 'Fides AI',
  /// );
  /// ```
  Future<void> showAIResponseNotification(
    String message, {
    String? customTitle,
    NotificationPriority priority = NotificationPriority.high,
    bool showTimestamp = true,
  }) async {
    final title = customTitle ?? 'AI Assistant';
    
    // Truncate message if too long (notification body limits)
    final truncatedMessage = message.length > 200 
        ? '${message.substring(0, 197)}...' 
        : message;
    
    // Determine Android importance and priority based on parameter
    final Importance androidImportance;
    final Priority androidPriority;
    
    switch (priority) {
      case NotificationPriority.high:
        androidImportance = Importance.high;
        androidPriority = Priority.high;
        break;
      case NotificationPriority.low:
        androidImportance = Importance.low;
        androidPriority = Priority.low;
        break;
      case NotificationPriority.defaultPriority:
        androidImportance = Importance.defaultImportance;
        androidPriority = Priority.defaultPriority;
        break;
    }
    
    final AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'connectx_ai_responses',
      'AI Responses',
      channelDescription: 'Notifications for AI Assistant responses',
      importance: androidImportance,
      priority: androidPriority,
      showWhen: showTimestamp,
      styleInformation: BigTextStyleInformation(
        truncatedMessage,
        contentTitle: title,
        summaryText: 'AI Response',
      ),
      icon: '@mipmap/ic_launcher',
    );

    const DarwinNotificationDetails iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
      interruptionLevel: InterruptionLevel.timeSensitive,
    );

    final NotificationDetails notificationDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    // Use timestamp as ID to allow multiple AI response notifications
    final notificationId = DateTime.now().millisecondsSinceEpoch ~/ 1000;

    await _notificationsPlugin.show(
      notificationId,
      title,
      truncatedMessage,
      notificationDetails,
      payload: 'ai_response:$notificationId',
    );

    debugPrint('NotificationService: Showed AI response notification - $title');
  }

  /// Show notification for connection status
  Future<void> showConnectionNotification({
    required bool isConnected,
    String? message,
  }) async {
    await showNotification(
      id: 1, // Fixed ID for connection notifications
      title: isConnected ? 'Connected' : 'Disconnected',
      body: message ?? (isConnected 
          ? 'Successfully connected to AI Assistant'
          : 'Disconnected from AI Assistant'),
      payload: 'connection_status',
    );
  }

  /// Show notification for errors
  Future<void> showErrorNotification(String error) async {
    await showNotification(
      id: 2, // Fixed ID for error notifications
      title: 'Error',
      body: error,
      payload: 'error',
    );
  }

  /// Cancel a specific notification
  Future<void> cancelNotification(int id) async {
    await _notificationsPlugin.cancel(id);
    debugPrint('NotificationService: Cancelled notification $id');
  }

  /// Cancel all notifications
  Future<void> cancelAllNotifications() async {
    await _notificationsPlugin.cancelAll();
    debugPrint('NotificationService: Cancelled all notifications');
  }

  /// Handle notification tap
  void _onNotificationTapped(NotificationResponse response) {
    debugPrint('NotificationService: Notification tapped - ${response.payload}');
    // Handle navigation or actions based on payload
    // This can be extended to navigate to specific screens
  }

  /// Get pending notifications
  Future<List<PendingNotificationRequest>> getPendingNotifications() async {
    return await _notificationsPlugin.pendingNotificationRequests();
  }

  /// Check if notifications are enabled
  Future<bool> areNotificationsEnabled() async {
    if (!_isInitialized) return false;

    // Check Android
    final androidImplementation = _notificationsPlugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    
    if (androidImplementation != null) {
      final bool? enabled = await androidImplementation.areNotificationsEnabled();
      return enabled ?? false;
    }

    // For iOS, assume enabled if initialized
    return _isInitialized;
  }
}
