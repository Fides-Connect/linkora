import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'wrappers.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException: $message (Status: $statusCode)';
}

/// Low-level HTTP client for the Linkora AI-assistant REST API.
///
/// All public methods return `Future<dynamic>` because the HTTP boundary does
/// not carry static type information — the JSON decoder may produce a
/// `Map<String, dynamic>`, a `List<dynamic>`, a raw `String`, or `null`
/// depending on the endpoint.  Typed wrappers (e.g., repositories) are the
/// callers' responsibility for casting or deserialising decoded values.
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

  /// Sends a GET request to [endpoint] (relative path, e.g. `/api/v1/me`).
  ///
  /// Returns the decoded response body:
  /// - `Map<String, dynamic>` for JSON object responses
  /// - `List<dynamic>` for JSON array responses
  /// - `String` if the body is non-empty but not valid JSON
  /// - `null` if the response body is empty
  ///
  /// Throws [ApiException] on non-2xx status codes, request timeout, or
  /// network failure.
  Future<dynamic> get(String endpoint) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('GET $url');
    return _performRequest(() => _client.get(url, headers: headers).timeout(_timeout));
  }

  /// Sends a POST request to [endpoint] with an optional JSON-encoded [body].
  ///
  /// Returns the decoded response body:
  /// - `Map<String, dynamic>` for JSON object responses
  /// - `List<dynamic>` for JSON array responses
  /// - `String` if the body is non-empty but not valid JSON
  /// - `null` if the response body is empty (e.g. 201 with no content)
  ///
  /// Throws [ApiException] on non-2xx status codes, request timeout, or
  /// network failure.
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

  /// Sends a PUT request to [endpoint] with an optional JSON-encoded [body].
  ///
  /// Returns the decoded response body:
  /// - `Map<String, dynamic>` for JSON object responses
  /// - `List<dynamic>` for JSON array responses
  /// - `String` if the body is non-empty but not valid JSON
  /// - `null` if the response body is empty
  ///
  /// Throws [ApiException] on non-2xx status codes, request timeout, or
  /// network failure.
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

  /// Sends a PATCH request to [endpoint] with an optional JSON-encoded [body].
  /// Typically used for partial updates, e.g. `PATCH /api/v1/me`.
  ///
  /// Returns the decoded response body:
  /// - `Map<String, dynamic>` for JSON object responses
  /// - `List<dynamic>` for JSON array responses
  /// - `String` if the body is non-empty but not valid JSON
  /// - `null` if the response body is empty
  ///
  /// Throws [ApiException] on non-2xx status codes, request timeout, or
  /// network failure.
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

  /// Sends a DELETE request to [endpoint].
  /// Typically used to remove resources, e.g. `DELETE /api/v1/me/competencies/{id}`.
  ///
  /// Returns the decoded response body:
  /// - `Map<String, dynamic>` for JSON object responses
  /// - `null` if the response body is empty (common for 204 No Content)
  ///
  /// Throws [ApiException] on non-2xx status codes, request timeout, or
  /// network failure.
  Future<dynamic> delete(String endpoint) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = await _getHeaders();

    debugPrint('DELETE $url');
    return _performRequest(() => _client.delete(url, headers: headers).timeout(_timeout));
  }

  /// Executes [request], enforces the shared timeout, and delegates status
  /// checking to [_processResponse].
  ///
  /// Returns the same value as [_processResponse] — decoded JSON body, raw
  /// `String`, or `null`.
  ///
  /// Throws [ApiException] wrapping any [TimeoutException], [SocketException],
  /// or unexpected error.
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

  /// Validates [response] and converts the body into a convenient Dart value.
  ///
  /// Successful `2xx` responses are decoded as follows:
  /// - JSON object or array bodies are returned via `jsonDecode`
  /// - empty bodies return `null`
  /// - non-JSON bodies fall back to the raw response text
  ///
  /// Non-success responses throw [ApiException] with the original status code.
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
