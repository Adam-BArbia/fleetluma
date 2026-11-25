import 'package:fleetluma/data/fleet_api.dart';
import 'package:fleetluma/ui/web_http_services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('service listing uses authenticated workspace scope', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => 'test-token',
      workspaceIdProvider: () async => 'workspace-1',
    );
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/services');
      expect(request.url.queryParameters['workspace_id'], 'workspace-1');
      expect(request.headers['Authorization'], 'Bearer test-token');
      return http.Response('{"items":[{"id":"service-1",'
        '"name":"FleetLuma Demo","url":"https://demo.example.org/health",'
        '"enabled":true,"status":"HEALTHY",'
        '"checked_at":"2026-11-25T09:00:00Z",'
        '"latency_ms":19.5}]}', 200);
    });
    final services = await fetchWebServices(api, client: client);
    expect(services.single.hostname, 'demo.example.org');
    expect(services.single.latencyMs, 19.5);
    expect(services.single.status, 'HEALTHY');
  });

  test('service checks preserve failure and unavailable latency', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => 'test-token',
    );
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/services/service-1/checks');
      expect(request.url.queryParameters['window'], '1h');
      return http.Response('{"items":[{"checked_at":"2026-11-25T09:05:00Z",'
        '"status":"UNHEALTHY","http_code":null,"latency_ms":null,'
        '"failure_kind":"timeout"}]}', 200);
    });
    final rows = await fetchWebServiceChecks(
      api, 'service-1', '1h', client: client);
    expect(rows.single.status, 'UNHEALTHY');
    expect(rows.single.latencyMs, isNull);
    expect(rows.single.failureKind, 'timeout');
  });

  test('workspace is required before fetching services', () async {
    var called = false;
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => 'test-token',
      workspaceIdProvider: () async => null,
    );
    await expectLater(
      fetchWebServices(api, client: MockClient((_) async {
        called = true;
        return http.Response('{}', 200);
      })),
      throwsA(isA<FleetAccessDeniedException>()),
    );
    expect(called, isFalse);
  });

  test('unknown service and invalid window never reveal data', () async {
    final api = HttpFleetApi(
      baseUrl: 'https://fleetluma-api.vercel.app',
      tokenProvider: () async => 'test-token',
    );
    await expectLater(
      fetchWebServiceChecks(api, 'private-service', '1h',
        client: MockClient((_) async => http.Response('', 404))),
      throwsA(isA<FleetAccessDeniedException>()),
    );
    await expectLater(
      fetchWebServiceChecks(api, 'service-1', '7d'),
      throwsFormatException,
    );
  });
}
