import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fleetluma/data/fleet_api.dart';
import 'package:fleetluma/ui/web_host_history.dart';

void main() {
  test('history window selection accepts only backend-supported ranges', () {
    expect(historyWindow('15m'), const Duration(minutes: 15));
    expect(historyWindow('1h'), const Duration(hours: 1));
    expect(historyWindow('24h'), const Duration(hours: 24));
    expect(() => historyWindow('7d'), throwsFormatException);
  });

  test('parses recorded sample values and rejects incorrect measurements', () {
    const timestamp = '2026-11-23T10:11:12Z';
    final good = HostHistoryPoint.fromJson({
      'received_at': timestamp,
      'cpu_pct': 23.1,
      'ram_pct': 61,
      'disk_pct': 48.8,
    });
    expect(good.cpu, 23.1);
    expect(good.ram, 61);
    expect(good.disk, 48.8);
    expect(good.time.isUtc, true);
    expect(
      () => HostHistoryPoint.fromJson({
        'received_at': timestamp,
        'cpu_pct': 101,
        'ram_pct': 20,
        'disk_pct': 50,
      }),
      throwsFormatException,
    );
  });

  test('history request uses authenticated host endpoint, sorted samples',
      () async {
    final captured = <String, String>{};
    final client = MockClient((req) async {
      captured['path'] = req.url.path;
      captured['window'] = req.url.queryParameters['window'] ?? '';
      captured['auth'] = req.headers['Authorization'] ?? '';
      return http.Response(jsonEncode({
        'host_id': 'example-host',
        'window': '15m',
        'items': [
          {'received_at': '2026-11-23T10:10:02Z',
           'cpu_pct': 32, 'ram_pct': 42, 'disk_pct': 52},
          {'received_at': '2026-11-23T10:10:01Z',
           'cpu_pct': 31, 'ram_pct': 41, 'disk_pct': 51},
        ],
      }), 200);
    });
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.example.test',
      tokenProvider: () async => 'test-token-not-a-real-secret',
    );
    final points = await fetchHostHistory(api, 'example-host', '15m',
        client: client);
    expect(captured['path'], '/api/v1/hosts/example-host/history');
    expect(captured['window'], '15m');
    expect(captured['auth'], 'Bearer test-token-not-a-real-secret');
    expect(points.length, 2);
    expect(points.first.cpu, 31);
    expect(points.last.cpu, 32);
    client.close();
  });

  test('history access must fail on 401', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.example.test',
      tokenProvider: () async => 'test',
    );
    final client = MockClient((_) async => http.Response('{}', 401));
    await expectLater(
      fetchHostHistory(api, 'example-host', '1h', client: client),
      throwsA(isA<FleetSessionExpiredException>()),
    );
    client.close();
  });
}
