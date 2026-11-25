import 'package:fleetluma/util/csv_report.dart';
import 'package:fleetluma/ui/web_host_history.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('CSV serializes actual historical CPU RAM disk samples', () {
    final csv = makeHostHistoryCsv(
      hostId: 'device-1',
      window: '1h',
      samples: [
        HostHistoryPoint(DateTime.utc(2026, 11, 25, 9), 12.3, 45.6, 78.9)
      ],
    );
    expect(csv, contains('received_at_utc,cpu_pct,ram_pct,disk_pct'));
    expect(csv, contains('"2026-11-25T09:00:00.000Z","12.30","45.60","78.90"'));
  });

  test('CSV protects spreadsheet formula injection in device names', () {
    final csv = makeHostHistoryCsv(
      hostId: '=HYPERLINK("https://example.invalid")',
      window: '15m',
      samples: [
        HostHistoryPoint(DateTime.utc(2026, 11, 25), 1, 2, 3)
      ],
    );
    expect(csv, contains("'=HYPERLINK"));
  });

  test('CSV cannot silently accept invalid query window', () {
    expect(() => makeHostHistoryCsv(hostId: 'a', window: '30d', samples: []),
      throwsArgumentError);
  });
}
