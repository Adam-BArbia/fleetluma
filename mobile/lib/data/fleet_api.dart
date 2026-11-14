import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/host_snapshot.dart';

abstract class FleetApi {
  Future<List<HostSnapshot>> fetchHosts();
}

/// Cross-platform REST client for Android and Flutter Web.
///
/// Uses package:http's platform-specific implementation (IO on Android,
/// BrowserClient on web). The production app never uses mock host records.
class HttpFleetApi implements FleetApi {
  final Uri baseUri;
  final Duration timeout;
  final http.Client? _injectedClient;

  HttpFleetApi({
    required String baseUrl,
    this.timeout = const Duration(seconds: 5),
    http.Client? client,
  })  : _injectedClient = client,
        baseUri = Uri.parse(baseUrl) {
    if (!baseUri.hasAuthority ||
        (baseUri.scheme != 'http' && baseUri.scheme != 'https')) {
      throw ArgumentError.value(baseUrl, 'baseUrl', 'Expected HTTP(S) URL');
    }
  }

  @override
  Future<List<HostSnapshot>> fetchHosts() async {
    final client = _injectedClient ?? http.Client();
    try {
      final endpoint = baseUri.replace(
        path: '${baseUri.path.replaceFirst(RegExp(r'/$'), '')}/api/v1/hosts',
      );
      final response = await client
          .get(endpoint, headers: {'Accept': 'application/json'})
          .timeout(timeout);
      if (response.statusCode != 200) {
        throw FleetConnectionException(
          'Coordinator returned HTTP ${response.statusCode}.',
        );
      }
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic> || decoded['items'] is! List) {
        throw const FormatException('Unexpected fleet response shape');
      }
      final items = decoded['items'] as List<dynamic>;
      return items
          .map((item) => HostSnapshot.fromJson(
                Map<String, dynamic>.from(item as Map),
              ))
          .toList(growable: false);
    } on TimeoutException {
      throw const FleetConnectionException(
        'Coordinator request timed out. Check the backend address.',
      );
    } on http.ClientException {
      throw const FleetConnectionException(
        'Cannot reach the coordinator. Check your network and backend URL.',
      );
    } on FormatException {
      throw const FleetConnectionException('The server returned invalid data.');
    } on TypeError {
      throw const FleetConnectionException('Unexpected API response format.');
    } finally {
      if (_injectedClient == null) client.close();
    }
  }
}

class FleetConnectionException implements Exception {
  final String message;
  const FleetConnectionException(this.message);

  @override
  String toString() => message;
}
