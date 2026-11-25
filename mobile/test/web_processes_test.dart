import 'package:fleetluma/data/fleet_api.dart';
import 'package:fleetluma/ui/web_host_processes.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('authorized process endpoint renders real CPU values above 100%', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => 'unit-test-token',
    );
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/hosts/host-1/processes');
      expect(request.headers['Authorization'], 'Bearer unit-test-token');
      return http.Response(
        '{"host_id":"host-1","captured_at":"2026-11-25T08:00:00Z",'
        '"processes":[{"pid":2468,"name":"python",'
        '"cpu_pct":105.2,"memory_bytes":230686720}]}', 200,
      );
    });
    final data = await fetchWebProcesses(api, 'host-1', client: client);
    expect(data.capturedAt, DateTime.utc(2026, 11, 25, 8));
    expect(data.processes.single.cpuPct, 105.2);
    expect(data.processes.single.memoryBytes, 230686720);
  });

  test('unauthorized process retrieval is denied', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => 'viewer-token',
    );
    await expectLater(
      fetchWebProcesses(api, 'other-workspace-host',
        client: MockClient((_) async => http.Response('', 404))),
      throwsA(isA<FleetAccessDeniedException>()),
    );
  });

  test('expired session never makes an HTTP request', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => null,
    );
    var called = false;
    await expectLater(
      fetchWebProcesses(api, 'host-1', client: MockClient((_) async {
        called = true;
        return http.Response('{}', 200);
      })),
      throwsA(isA<FleetSessionExpiredException>()),
    );
    expect(called, isFalse);
  });

  test('invalid process payload is rejected', () {
    expect(
      () => ProcessSnapshot.fromJson({
        'captured_at': '2026-11-25T08:00:00Z',
        'processes': [{'pid': 1, 'name': 'worker',
          'cpu_pct': -2, 'memory_bytes': 20}],
      }),
      throwsFormatException,
    );
  });
}
