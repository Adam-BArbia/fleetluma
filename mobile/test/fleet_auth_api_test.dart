import 'package:fleetluma/data/fleet_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('Cloud requests attach operator JWT to HTTP headers', () async {
    final mock = MockClient((request) async {
      expect(request.headers['Authorization'], 'Bearer jwt-test-token');
      return http.Response('{"items":[]}', 200,
          headers: {'Content-Type': 'application/json'});
    });
    final client = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => 'jwt-test-token',
    );
    expect(await client.fetchHosts(), isEmpty);
    mock.close();
  });

  test('Missing cloud session refuses to send a request', () async {
    var called = false;
    final mock = MockClient((request) async {
      called = true;
      return http.Response('{"items":[]}', 200);
    });
    final client = HttpFleetApi(
      baseUrl: 'https://api.example.test',
      client: mock,
      tokenProvider: () async => null,
    );
    await expectLater(client.fetchHosts(),
        throwsA(isA<FleetConnectionException>()));
    expect(called, isFalse);
    mock.close();
  });
}
