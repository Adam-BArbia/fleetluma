import 'dart:convert';

import 'package:fleetluma/data/fleet_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('Fetches FleetLuma host list over cross-platform client', () async {
    late Uri observed;
    final mock = MockClient((request) async {
      observed = request.url;
      expect(request.headers['Accept'], 'application/json');
      return http.Response(jsonEncode({
        'items': [
          {
            'id': 'b5c48d23-4b37-4b97-8c1d-53d5f16a90d4',
            'name': 'web-test',
            'os': 'linux',
            'status': 'PENDING',
            'last_seen_at': null,
            'latest_metrics': null
          }
        ]
      }), 200);
    });
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test/',
      client: mock,
    );
    final hosts = await api.fetchHosts();
    expect(observed.toString(), 'https://api.example.test/api/v1/hosts');
    expect(hosts.single.name, 'web-test');
    expect(hosts.single.metrics, isNull);
    mock.close();
  });

  test('Reports HTTP errors instead of presenting stale data as fresh', () async {
    final mock = MockClient((request) async => http.Response('unavailable', 503));
    final api = HttpFleetApi(baseUrl: 'https://api.example.test', client: mock);
    await expectLater(
      api.fetchHosts(),
      throwsA(isA<FleetConnectionException>()),
    );
    mock.close();
  });

  test('Rejects malformed fleet payloads', () async {
    final mock = MockClient((request) async => http.Response('{"items":{}}', 200));
    final api = HttpFleetApi(baseUrl: 'https://api.example.test', client: mock);
    await expectLater(api.fetchHosts(), throwsA(isA<FleetConnectionException>()));
    mock.close();
  });


  test('Cloud fleet shows approval guidance on HTTP 403', () async {
    final mock = MockClient((request) async {
      expect(request.headers['Authorization'], 'Bearer operator-jwt');
      return http.Response('{"error":"FORBIDDEN"}', 403);
    });
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'operator-jwt',
    );
    await expectLater(
      api.fetchHosts(),
      throwsA(isA<FleetConnectionException>().having(
        (error) => error.message, 'message', contains('not yet approved'),
      )),
    );
    mock.close();
  });

  test('Cloud fleet handles HTTP 401 as an expired session', () async {
    final mock = MockClient((request) async => http.Response('', 401));
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'expired-operator-jwt',
    );
    await expectLater(
      api.fetchHosts(),
      throwsA(isA<FleetConnectionException>().having(
        (error) => error.message, 'message', contains('Session expired'),
      )),
    );
    mock.close();
  });

  test('Rejects malformed backend URL', () {
    expect(
      () => HttpFleetApi(baseUrl: 'nope'),
      throwsArgumentError,
    );
  });

  test('Workspace-enforced fleet sends scope alongside approved JWT', () async {
    late Uri observed;
    final mock = MockClient((request) async {
      observed = request.url;
      expect(request.headers['Authorization'], 'Bearer approved-jwt');
      return http.Response('{"items":[]}', 200);
    });
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'approved-jwt',
      workspaceIdProvider: () async => 'workspace-123',
    );
    expect(await api.fetchHosts(), isEmpty);
    expect(observed.queryParameters['workspace_id'], 'workspace-123');
    mock.close();
  });

  test('Workspace-enforced fleet refuses unscoped requests', () async {
    var requests = 0;
    final mock = MockClient((request) async {
      requests++;
      return http.Response('{"items":[]}', 200);
    });
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'approved-jwt',
      workspaceIdProvider: () async => null,
    );
    await expectLater(api.fetchHosts(), throwsA(isA<FleetAccessDeniedException>()));
    expect(requests, 0);
    mock.close();
  });

}
