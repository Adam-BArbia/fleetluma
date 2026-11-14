import 'package:fleetluma/data/fleet_api.dart';
import 'package:fleetluma/models/host_snapshot.dart';
import 'package:fleetluma/state/fleet_controller.dart';
import 'package:fleetluma/ui/fleet_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeFleetApi implements FleetApi {
  List<HostSnapshot> response = const [];
  Object? exception;

  @override
  Future<List<HostSnapshot>> fetchHosts() async {
    if (exception != null) throw exception!;
    return response;
  }
}

HostSnapshot host({AgentStatus status = AgentStatus.connected}) =>
    HostSnapshot(
      id: 'b5c48d23-4b37-4b97-8c1d-53d5f16a90d4',
      name: 'dev-server-01',
      os: 'linux',
      status: status,
      lastSeenAt: DateTime.now().toUtc(),
      metrics: HostMetrics(
        cpuPct: 42,
        ramPct: 68,
        diskPct: 31,
        ramUsedBytes: 680,
        ramTotalBytes: 1000,
        diskUsedBytes: 310,
        diskTotalBytes: 1000,
        diskPath: '/',
        sampledAt: DateTime.now().toUtc(),
        receivedAt: DateTime.now().toUtc(),
      ),
    );

Widget app(FleetController state) => MaterialApp(
      home: FleetScreen(
        controller: state,
        apiUrl: 'http://10.0.2.2:8000',
      ),
    );

void main() {
  testWidgets('empty fleet shows provisioning guidance', (tester) async {
    final controller = FleetController(api: FakeFleetApi());
    await tester.pumpWidget(app(controller));
    await tester.pumpAndSettle();
    expect(find.text('No hosts registered yet'), findsOneWidget);
    expect(find.text('Fleet overview'), findsOneWidget);
  });

  testWidgets('connected host shows resource values', (tester) async {
    final api = FakeFleetApi()..response = [host()];
    final controller = FleetController(api: api);
    await tester.pumpWidget(app(controller));
    await tester.pumpAndSettle();
    expect(find.text('dev-server-01'), findsOneWidget);
    expect(find.text('CONNECTED'), findsOneWidget);
    expect(find.text('42%'), findsOneWidget);
    expect(find.text('68%'), findsOneWidget);
    expect(find.text('31%'), findsOneWidget);
  });

  testWidgets('stale host is explicitly not marked live', (tester) async {
    final api = FakeFleetApi()..response = [host(status: AgentStatus.stale)];
    final controller = FleetController(api: api);
    await tester.pumpWidget(app(controller));
    await tester.pumpAndSettle();
    expect(find.text('STALE'), findsOneWidget);
    expect(find.text('LAST KNOWN READINGS · NOT LIVE'), findsOneWidget);
  });

  testWidgets('API failure shows retry and readable error', (tester) async {
    final api = FakeFleetApi()
      ..exception = const FleetConnectionException('Coordinator unreachable');
    final controller = FleetController(api: api);
    await tester.pumpWidget(app(controller));
    await tester.pumpAndSettle();
    expect(find.textContaining('Coordinator unreachable'), findsWidgets);
    expect(find.text('Retry'), findsOneWidget);
  });
}
