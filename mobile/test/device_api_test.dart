import 'dart:convert';

import 'package:fleetluma/data/device_api.dart';
import 'package:fleetluma/data/fleet_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('operator workspace reads are JWT authenticated and do not redirect', () async {
    var requests = 0;
    final client = MockClient((request) async {
      requests++;
      expect(request.url.path, '/api/v1/operator/workspaces');
      expect(request.followRedirects, isFalse);
      expect(request.maxRedirects, 0);
      expect(request.headers['Authorization'], 'Bearer approved-jwt');
      return http.Response(jsonEncode({
        'items': [
          {'id': 'workspace-1', 'name': 'Personal Fleet', 'role': 'owner'},
          {'id': 'workspace-2', 'name': 'Read-only Fleet', 'role': 'viewer'},
        ],
      }), 200);
    });
    final api = HttpFleetDeviceApi(
      baseUrl: 'https://api.example.test',
      tokenProvider: () async => 'approved-jwt',
      client: client,
    );
    final workspaces = await api.workspaces();
    expect(workspaces.length, 2);
    expect(workspaces.first.canManage, isTrue);
    expect(workspaces.last.canManage, isFalse);
    expect(requests, 1);
    client.close();
  });

  test('missing session never calls enrollment endpoints', () async {
    var requests = 0;
    final client = MockClient((request) async {
      requests++;
      return http.Response('{}', 200);
    });
    final api = HttpFleetDeviceApi(
      baseUrl: 'https://api.example.test',
      tokenProvider: () async => null,
      client: client,
    );
    await expectLater(api.workspaces(), throwsA(isA<FleetSessionExpiredException>()));
    expect(requests, 0);
    client.close();
  });

  test('operator JWT is not followed across a redirect', () async {
    final client = MockClient((request) async {
      expect(request.followRedirects, isFalse);
      return http.Response('', 302, headers: {
        'location': 'https://unexpected.invalid/jwt-capture',
      });
    });
    final api = HttpFleetDeviceApi(
      baseUrl: 'https://api.example.test',
      tokenProvider: () async => 'approved-jwt',
      client: client,
    );
    await expectLater(api.workspaces(), throwsA(isA<FleetConnectionException>()));
    client.close();
  });

  test('safe pairing review never includes an agent reporting credential', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/api/v1/operator/pairings/resolve');
      expect(jsonDecode(request.body)['user_code'], 'ABCD-7294');
      expect(request.headers['Authorization'], 'Bearer approved-jwt');
      return http.Response(jsonEncode({
        'pairing_id': 'pair-1',
        'hostname': 'TUFFEST',
        'platform': 'windows',
        'agent_version': '0.1.0',
        'capabilities': ['cpu', 'ram'],
        'expires_at': '2030-01-01T00:00:00Z',
      }), 200);
    });
    final api = HttpFleetDeviceApi(
      baseUrl: 'https://api.example.test',
      tokenProvider: () async => 'approved-jwt',
      client: client,
    );
    final preview = await api.resolveCode('abcd-7294');
    expect(preview.hostname, 'TUFFEST');
    expect(preview.capabilities, ['cpu', 'ram']);
    client.close();
  });
}
