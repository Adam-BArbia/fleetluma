import 'package:fleetluma/data/fleet_api.dart';
import 'package:fleetluma/ui/web_alerts.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('rules are listed with workspace-bound bearer token', () async {
    final api=HttpFleetApi(
      baseUrl:'https://fleetluma-api.vercel.app',
      tokenProvider:() async=>'test-access-token',
      workspaceIdProvider:() async=>'workspace-1');
    final transport=MockClient((request) async {
      expect(request.url.path,'/api/v1/alerts/rules');
      expect(request.url.queryParameters['workspace_id'],'workspace-1');
      expect(request.headers['Authorization'],'Bearer test-access-token');
      return http.Response('{"items":[{"id":"rule-1","threshold_pct":85}]}',200);
    });
    final rows=await fetchAlertCollection(api,'rules',client:transport);
    expect(rows.single['id'],'rule-1');
  });

  test('missing workspace fails before any HTTP call',() async {
    var contacted=false;
    final api=HttpFleetApi(
      baseUrl:'https://fleetluma-api.vercel.app',
      tokenProvider:() async=>'test-access-token',
      workspaceIdProvider:() async=>null);
    await expectLater(fetchAlertCollection(api,'incidents',
        client:MockClient((_) async {
          contacted=true;
          return http.Response('{}',200);
        })), throwsA(isA<FleetAccessDeniedException>()));
    expect(contacted,isFalse);
  });

  test('server-level role restriction cannot be bypassed',() async {
    final api=HttpFleetApi(
      baseUrl:'https://fleetluma-api.vercel.app',
      tokenProvider:() async=>'viewer-token',
      workspaceIdProvider:() async=>'workspace-1');
    await expectLater(alertRequest(api,'POST',['rules'],
      body:{'metric':'cpu_pct','threshold_pct':80},
      client:MockClient((_) async => http.Response('{}',403))),
      throwsA(isA<FleetAccessDeniedException>()));
  });

  test('missing session cannot send a mutation',() async {
    var called=false;
    final api=HttpFleetApi(
      baseUrl:'https://fleetluma-api.vercel.app',
      tokenProvider:() async=>null);
    await expectLater(alertRequest(api,'DELETE',['rules','rule-1'],
      client:MockClient((_) async {
        called=true; return http.Response('{}',200);
      })), throwsA(isA<FleetSessionExpiredException>()));
    expect(called,isFalse);
  });
}
