import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'wrappers.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException: $message (Status: $statusCode)';
}

class ApiService {
  final FirebaseAuthWrapper _auth;
  final http.Client _client;
  late final String _baseUrl;
  static const Duration _timeout = Duration(seconds: 30);

  ApiService({FirebaseAuthWrapper? auth, http.Client? client, String? baseUrl})
      : _auth = auth ?? FirebaseAuthWrapper(),
        _client = client ?? http.Client() {
    if (baseUrl != null) {
      _baseUrl = baseUrl;
    } else {
      final serverUrl = dotenv.env['AI_ASSISTANT_SERVER_URL'] ?? 'localhost:8080';
      _baseUrl = serverUrl.startsWith('http') ? serverUrl : 'http://$serverUrl';
    }
  }

  Future<Map<String, String>> _getHeaders() async {
    final headers = {
      'Content-Type': 'application/json',
    };

    try {
      final user = _auth.currentUser;
      if (user != null) {
        final token = await user.getIdToken();
        if (token != null) {
          headers['Authorization'] = 'Bearer $token';
        }
      }
    } catch (e) {
      debugPrint('Error getting auth token: $e');
    }

    return headers;
  }

  Future<dynamic> get(String endpoint) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('GET $url');
    return _performRequest(() => _client.get(url, headers: headers).timeout(_timeout));
  }

  Future<dynamic> post(String endpoint, {dynamic body}) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('POST $url');
    return _performRequest(() => _client.post(
      url,
      headers: headers,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(_timeout));
  }

  Future<dynamic> put(String endpoint, {dynamic body}) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('PUT $url');
    return _performRequest(() => _client.put(
      url,
      headers: headers,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(_timeout));
  }

  Future<dynamic> patch(String endpoint, {dynamic body}) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('PATCH $url');
    return _performRequest(() => _client.patch(
      url,
      headers: headers,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(_timeout));
  }

  Future<dynamic> delete(String endpoint) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('DELETE $url');
    return _performRequest(() => _client.delete(url, headers: headers).timeout(_timeout));
  }

  Future<dynamic> _performRequest(Future<http.Response> Function() request) async {
    try {
      final response = await request();
      return _processResponse(response);
    } on TimeoutException {
      debugPrint('API Error: Request timed out');
      throw ApiException('Request timed out', statusCode: 408);
    } on SocketException {
      debugPrint('API Error: Network connection failed');
      throw ApiException('Network connection failed');
    } catch (e) {
      if (e is ApiException) rethrow;
      debugPrint('API Error: Unexpected error $e');
      throw ApiException('Unexpected error: $e');
    }
  }

  dynamic _processResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      try {
        return jsonDecode(response.body);
      } catch (e) {
        // If the response body is not valid JSON, return it as a raw string.
        return response.body;
      }
    } else {
      debugPrint('API Error: ${response.statusCode} ${response.body}');
      throw ApiException(
        'Request failed: ${response.body}',
        statusCode: response.statusCode,
      );
    }
  }
}
