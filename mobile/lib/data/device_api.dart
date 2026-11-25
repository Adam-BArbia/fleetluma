import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'fleet_api.dart';

/// Typed operator API for device enrollment; agent secrets never reach Flutter.
class FleetWorkspace {
  final String id;
  final String name;
  final String role;
  const FleetWorkspace({required this.id, required this.name, required this.role});
  bool get canManage => role == 'owner' || role == 'admin';

  factory FleetWorkspace.fromJson(Map<String, dynamic> data) => FleetWorkspace(
    id: data['id'] as String,
    name: data['name'] as String,
    role: data['role'] as String,
  );
}

class PairingPreview {
  final String pairingId;
  final String hostname;
  final String platform;
  final String agentVersion;
  final List<String> capabilities;
  final DateTime expiresAt;

  const PairingPreview({
    required this.pairingId,
    required this.hostname,
    required this.platform,
    required this.agentVersion,
    required this.capabilities,
    required this.expiresAt,
  });

  factory PairingPreview.fromJson(Map<String, dynamic> data) => PairingPreview(
    pairingId: data['pairing_id'] as String,
    hostname: data['hostname'] as String,
    platform: data['platform'] as String,
    agentVersion: data['agent_version'] as String,
    capabilities: (data['capabilities'] as List).cast<String>(),
    expiresAt: DateTime.parse(data['expires_at'] as String),
  );
}

class ManagedDevice {
  final String id;
  final String name;
  final String os;
  final String lifecycle;
  final String status;
  final String? lastSeenAt;
  const ManagedDevice({
    required this.id,
    required this.name,
    required this.os,
    required this.lifecycle,
    required this.status,
    this.lastSeenAt,
  });
  factory ManagedDevice.fromJson(Map<String, dynamic> data) => ManagedDevice(
    id: data['id'] as String,
    name: data['name'] as String,
    os: data['os'] as String,
    lifecycle: data['lifecycle'] as String,
    status: data['status'] as String,
    lastSeenAt: data['last_seen_at'] as String?,
  );
}

abstract class FleetDeviceApi {
  Future<List<FleetWorkspace>> workspaces();
  Future<PairingPreview> resolveCode(String code);
  Future<void> approve(String pairingId, String workspaceId);
  Future<void> deny(String pairingId);
  Future<List<ManagedDevice>> hosts(String workspaceId);
  Future<void> revoke(String hostId);
  Future<void> rename(String hostId, String newName);
}

class HttpFleetDeviceApi implements FleetDeviceApi {
  final Uri baseUri;
  final Future<String?> Function() tokenProvider;
  final Duration timeout;
  final http.Client? client;

  HttpFleetDeviceApi({
    required String baseUrl,
    required this.tokenProvider,
    this.client,
    this.timeout = const Duration(seconds: 10),
  }) : baseUri = Uri.parse(baseUrl) {
    if (!baseUri.hasAuthority ||
        (baseUri.scheme != 'https' && baseUri.scheme != 'http') ||
        baseUri.userInfo.isNotEmpty || baseUri.hasQuery || baseUri.hasFragment) {
      throw ArgumentError('Invalid coordinator origin');
    }
  }

  Future<Map<String, dynamic>> _request(
      String method, String path, {Map<String, dynamic>? body,
      Map<String, String>? query}) async {
    final jwt = await tokenProvider();
    if (jwt == null || jwt.isEmpty) {
      throw const FleetSessionExpiredException();
    }
    final uri = baseUri.replace(
      path: '/api/v1/operator/$path',
      queryParameters: query,
    );
    final headers = {
      'Accept': 'application/json',
      'Authorization': 'Bearer $jwt',
      if (body != null) 'Content-Type': 'application/json',
    };
    final httpClient = client ?? http.Client();
    try {
      final request = http.Request(method, uri)
        ..headers.addAll(headers)
        ..followRedirects = false
        ..maxRedirects = 0;
      if (body != null) request.body = jsonEncode(body);
      final streamed = await httpClient.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed).timeout(timeout);
      if (response.statusCode == 401) {
        throw const FleetSessionExpiredException();
      }
      if (response.statusCode == 403) {
        throw const FleetAccessDeniedException();
      }
      if (response.statusCode == 404 || response.statusCode == 410) {
        throw const FleetConnectionException(
          'Pairing request not found or expired. Check the code on the device.',
        );
      }
      if (response.statusCode == 429) {
        throw const FleetConnectionException('Too many attempts. Try again later.');
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw FleetConnectionException(
          'Coordinator rejected the operation (HTTP ${response.statusCode}).',
        );
      }
      if (response.statusCode == 204 || response.body.trim().isEmpty) return {};
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Expected an object response');
      }
      return decoded;
    } on TimeoutException {
      throw const FleetConnectionException('Coordinator request timed out.');
    } on http.ClientException {
      throw const FleetConnectionException('Coordinator is unreachable.');
    } on FormatException {
      throw const FleetConnectionException('Unexpected response from coordinator.');
    } finally {
      if (client == null) httpClient.close();
    }
  }

  @override
  Future<List<FleetWorkspace>> workspaces() async {
    final result = await _request('GET', 'workspaces');
    return (result['items'] as List)
      .map((e) => FleetWorkspace.fromJson(Map<String, dynamic>.from(e as Map)))
      .toList(growable: false);
  }

  @override
  Future<PairingPreview> resolveCode(String code) async {
    final result = await _request('POST', 'pairings/resolve', body: {
      'user_code': code.trim().toUpperCase(),
    });
    return PairingPreview.fromJson(result);
  }

  @override
  Future<void> approve(String pairingId, String workspaceId) async {
    await _request('POST', 'pairings/${Uri.encodeComponent(pairingId)}/approve',
        body: {'workspace_id': workspaceId});
  }

  @override
  Future<void> deny(String pairingId) async {
    await _request('POST', 'pairings/${Uri.encodeComponent(pairingId)}/deny');
  }

  @override
  Future<List<ManagedDevice>> hosts(String workspaceId) async {
    final result = await _request('GET', 'hosts',
        query: {'workspace_id': workspaceId});
    return (result['items'] as List)
      .map((e) => ManagedDevice.fromJson(Map<String, dynamic>.from(e as Map)))
      .toList(growable: false);
  }

  @override
  Future<void> rename(String hostId, String newName) async {
    final normalized = newName.trim();
    if (normalized.length < 2 || normalized.length > 64) {
      throw const FormatException('Device name must be 2–64 characters.');
    }
    await _request('PATCH', 'hosts/${Uri.encodeComponent(hostId)}',
        body: {'name': normalized});
  }

  @override
  Future<void> revoke(String hostId) async {
    await _request('POST', 'hosts/${Uri.encodeComponent(hostId)}/revoke');
  }
}
