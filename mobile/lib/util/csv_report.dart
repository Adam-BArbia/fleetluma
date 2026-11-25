import '../ui/web_host_history.dart';

/// Convert genuine previously fetched samples to an Excel-safe CSV export.
/// No local/demo values are generated. Report generation does not call an API.
String makeHostHistoryCsv({
  required String hostId,
  required String window,
  required List<HostHistoryPoint> samples,
}) {
  if (!const ['15m', '1h', '24h'].contains(window)) {
    throw ArgumentError.value(window, 'window', 'Unsupported time window');
  }
  final lines = <String>[
    'host_id,window,received_at_utc,cpu_pct,ram_pct,disk_pct',
  ];
  for (final sample in samples) {
    final row = [
      hostId,
      window,
      sample.time.toUtc().toIso8601String(),
      sample.cpu.toStringAsFixed(2),
      sample.ram.toStringAsFixed(2),
      sample.disk.toStringAsFixed(2),
    ];
    lines.add(row.map(safeCsvField).join(','));
  }
  return '\uFEFF' + lines.join('\r\n') + '\r\n';
}

/// Quoting alone does not neutralize spreadsheet formula injection.
/// Prefix cells starting with spreadsheet operator characters with a quote.
String safeCsvField(String field) {
  final dangerous = RegExp(r'^\s*[=+@-]');
  final normalized = dangerous.hasMatch(field) ? "'$field" : field;
  return '"${normalized.replaceAll('"', '""')}"';
}
