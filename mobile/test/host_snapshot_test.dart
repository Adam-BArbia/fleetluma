import 'package:fleetluma/models/host_snapshot.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final json = <String, dynamic>{
    'id': 'b5c48d23-4b37-4b97-8c1d-53d5f16a90d4',
    'name': 'demo-linux-01',
    'os': 'linux',
    'status': 'CONNECTED',
    'last_seen_at': '2026-11-14T11:30:01Z',
    'latest_metrics': <String, dynamic>{
      'cpu_pct': 42.5,
      'ram_used_bytes': 5368709120,
      'ram_total_bytes': 8589934592,
      'ram_pct': 62.5,
      'disk_path': '/',
      'disk_used_bytes': 107374182400,
      'disk_total_bytes': 214748364800,
      'disk_pct': 50,
      'sampled_at': '2026-11-14T11:30:00Z',
      'received_at': '2026-11-14T11:30:01Z',
    },
  };

  test('parses exact FL-6 response contract', () {
    final host = HostSnapshot.fromJson(json);
    expect(host.status, AgentStatus.connected);
    expect(host.name, 'demo-linux-01');
    expect(host.metrics!.ramPct, 62.5);
    expect(host.metrics!.diskUsedBytes, 107374182400);
    expect(host.lastSeenAt!.isUtc, true);
  });

  test('represents pending host with no metric data', () {
    final pending = HostSnapshot.fromJson({
      ...json,
      'status': 'PENDING',
      'last_seen_at': null,
      'latest_metrics': null,
    });
    expect(pending.status, AgentStatus.pending);
    expect(pending.metrics, isNull);
  });

  test('rejects unknown state', () {
    expect(
      () => HostSnapshot.fromJson({...json, 'status': 'DOWN'}),
      throwsFormatException,
    );
  });

  test('rejects metrics above 100%', () {
    expect(
      () => HostSnapshot.fromJson({
        ...json,
        'latest_metrics': {
          ...json['latest_metrics'] as Map<String, dynamic>,
          'cpu_pct': 101,
        },
      }),
      throwsFormatException,
    );
  });

  test('formats missing and old reports without claiming outage', () {
    final now = DateTime.utc(2026, 11, 14, 11, 30);
    expect(elapsedLabel(null, now), 'No reports yet');
    expect(elapsedLabel(now.subtract(const Duration(minutes: 3)), now),
        '3m ago');
  });
}
