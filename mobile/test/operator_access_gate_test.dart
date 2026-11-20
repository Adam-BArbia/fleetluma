import 'package:fleetluma/data/fleet_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('403 from backend is an explicit operator approval rejection', () async {
    final mock = MockClient((_) async => http.Response('{"error":"FORBIDDEN"}', 403));
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'test-operator-jwt',
    );
    await expectLater(api.fetchHosts(), throwsA(isA<FleetAccessDeniedException>()));
    mock.close();
  });

  test('401 from backend is a session rejection', () async {
    final mock = MockClient((_) async => http.Response('{"error":"UNAUTHORIZED"}', 401));
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'expired-test-jwt',
    );
    await expectLater(api.fetchHosts(), throwsA(isA<FleetSessionExpiredException>()));
    mock.close();
  });

  test('missing token refuses request before contacting coordinator', () async {
    var contacted = false;
    final mock = MockClient((_) async {
      contacted = true;
      return http.Response('{"items":[]}', 200);
    });
    final api = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => null,
    );
    await expectLater(api.fetchHosts(), throwsA(isA<FleetSessionExpiredException>()));
    expect(contacted, false);
    mock.close();
  });
}
