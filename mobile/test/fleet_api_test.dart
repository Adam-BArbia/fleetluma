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

  test('Rejects malformed backend URL', () {
    expect(
      () => HttpFleetApi(baseUrl: 'nope'),
      throwsArgumentError,
    );
  });
}
