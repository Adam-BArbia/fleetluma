import 'package:fleetluma/data/device_api.dart';
import 'package:fleetluma/ui/device_management_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeDeviceApi implements FleetDeviceApi {
  int resolveCalls = 0;
  int approveCalls = 0;
  int denyCalls = 0;
  int revokeCalls = 0;
  String? lastCode;
  String? lastWorkspace;
  bool approved = false;
  bool revoked = false;

  @override
  Future<List<FleetWorkspace>> workspaces() async => const [
    FleetWorkspace(id: 'workspace-1', name: 'Personal Fleet', role: 'owner'),
  ];

  @override
  Future<PairingPreview> resolveCode(String code) async {
    resolveCalls++;
    lastCode = code;
    return PairingPreview(
      pairingId: 'pairing-1', hostname: 'TUFFEST',
      platform: 'windows', agentVersion: '0.1.0',
      capabilities: const ['cpu', 'ram', 'disk'],
      expiresAt: DateTime.utc(2030, 1, 1),
    );
  }

  @override
  Future<void> approve(String pairingId, String workspaceId) async {
    expect(pairingId, 'pairing-1');
    approveCalls++;
    lastWorkspace = workspaceId;
    approved = true;
  }

  @override
  Future<void> deny(String pairingId) async { denyCalls++; }

  @override
  Future<List<ManagedDevice>> hosts(String workspaceId) async {
    if (!approved) return [];
    return [
      ManagedDevice(
        id: 'host-1', name: 'TUFFEST', os: 'windows',
        lifecycle: revoked ? 'REVOKED' : 'ACTIVE',
        status: revoked ? 'REVOKED' : 'CONNECTED',
      ),
    ];
  }

  @override
  Future<void> revoke(String hostId) async {
    expect(hostId, 'host-1');
    revokeCalls++;
    revoked = true;
  }
}

void main() {
  testWidgets('operator reviews and approves the computer code', (tester) async {
    final api = FakeDeviceApi();
    await tester.pumpWidget(MaterialApp(home: DeviceManagementScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Pair a new computer'), findsOneWidget);
    expect(find.text('Personal Fleet'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'abcd-7294');
    await tester.tap(find.text('Review device'));
    await tester.pumpAndSettle();
    expect(api.lastCode, 'ABCD-7294');
    expect(find.textContaining('Computer: TUFFEST'), findsOneWidget);
    expect(api.approveCalls, 0);
    await tester.tap(find.text('Approve and connect'));
    await tester.pumpAndSettle();
    expect(api.approveCalls, 1);
    expect(api.lastWorkspace, 'workspace-1');
    expect(find.text('TUFFEST'), findsOneWidget);
  });

  testWidgets('operator explicitly confirms revocation', (tester) async {
    final api = FakeDeviceApi()..approved = true;
    await tester.pumpWidget(MaterialApp(home: DeviceManagementScreen(api: api)));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Revoke TUFFEST'));
    await tester.pumpAndSettle();
    expect(api.revokeCalls, 0);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(api.revokeCalls, 0);
    await tester.tap(find.byTooltip('Revoke TUFFEST'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Revoke').last);
    await tester.pumpAndSettle();
    expect(api.revokeCalls, 1);
    expect(find.text('Revoked'), findsOneWidget);
  });

  testWidgets('invalid display code cannot be submitted', (tester) async {
    final api = FakeDeviceApi();
    await tester.pumpWidget(MaterialApp(home: DeviceManagementScreen(api: api)));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'INVALID');
    await tester.tap(find.text('Review device'));
    await tester.pumpAndSettle();
    expect(api.resolveCalls, 0);
    expect(find.textContaining('eight-character code'), findsOneWidget);
  });
}
