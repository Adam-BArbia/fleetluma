import 'dart:convert';
import 'dart:io';

import '../models/host_snapshot.dart';

abstract class FleetApi {
  Future<List<HostSnapshot>> fetchHosts();
}

/// Local-lab REST client. The Android app requires an address reachable
/// from the device, not the device's own 127.0.0.1.
class HttpFleetApi implements FleetApi {
  final Uri baseUri;
  final Duration timeout;

  HttpFleetApi({
    required String baseUrl,
    this.timeout = const Duration(seconds: 5),
  }) : baseUri = Uri.parse(baseUrl) {
    if (!baseUri.hasAuthority ||
        (baseUri.scheme != 'http' && baseUri.scheme != 'https')) {
      throw ArgumentError.value(baseUrl, 'baseUrl', 'Expected HTTP(S) URL');
    }
  }

  @override
  Future<List<HostSnapshot>> fetchHosts() async {
    final client = HttpClient()..connectionTimeout = timeout;
    try {
      final endpoint = baseUri.replace(
        path: '${baseUri.path.replaceFirst(RegExp(r'/$'), '')}/api/v1/hosts',
      );
      final request = await client.getUrl(endpoint).timeout(timeout);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(timeout);
      final payload = await utf8.decoder.bind(response).join().timeout(timeout);
      if (response.statusCode != HttpStatus.ok) {
        throw HttpException('Server returned HTTP ${response.statusCode}');
      }
      final json = jsonDecode(payload) as Map<String, dynamic>;
      final items = json['items'] as List<dynamic>;
      return items.map((item) {
        return HostSnapshot.fromJson(Map<String, dynamic>.from(item as Map));
      }).toList(growable: false);
    } on SocketException {
      throw const FleetConnectionException(
        'Cannot reach the coordinator. Check its address, firewall, and Wi-Fi.',
      );
    } on HandshakeException {
      throw const FleetConnectionException('Secure connection failed.');
    } on HttpException catch (error) {
      throw FleetConnectionException(error.message);
    } on FormatException {
      throw const FleetConnectionException('The server returned invalid data.');
    } on TypeError {
      throw const FleetConnectionException('Unexpected API response format.');
    } finally {
      client.close(force: true);
    }
  }
}

class FleetConnectionException implements Exception {
  final String message;
  const FleetConnectionException(this.message);

  @override
  String toString() => message;
}
