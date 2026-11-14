/// Models for FL-6 GET /api/v1/hosts. No synthetic data is created here.
enum AgentStatus { pending, connected, stale }

AgentStatus parseAgentStatus(String value) => switch (value) {
  'PENDING' => AgentStatus.pending,
  'CONNECTED' => AgentStatus.connected,
  'STALE' => AgentStatus.stale,
  _ => throw FormatException('Unknown host status: $value'),
};

class HostMetrics {
  final double cpuPct;
  final double ramPct;
  final double diskPct;
  final int ramUsedBytes;
  final int ramTotalBytes;
  final int diskUsedBytes;
  final int diskTotalBytes;
  final String diskPath;
  final DateTime sampledAt;
  final DateTime receivedAt;

  const HostMetrics({
    required this.cpuPct,
    required this.ramPct,
    required this.diskPct,
    required this.ramUsedBytes,
    required this.ramTotalBytes,
    required this.diskUsedBytes,
    required this.diskTotalBytes,
    required this.diskPath,
    required this.sampledAt,
    required this.receivedAt,
  });

  factory HostMetrics.fromJson(Map<String, dynamic> value) {
    double percent(String key) {
      final number = (value[key] as num).toDouble();
      if (!number.isFinite || number < 0 || number > 100) {
        throw FormatException('Invalid $key percentage');
      }
      return number;
    }

    int bytes(String key) {
      final n = value[key] as int;
      if (n < 0) throw FormatException('Invalid $key');
      return n;
    }

    return HostMetrics(
      cpuPct: percent('cpu_pct'),
      ramPct: percent('ram_pct'),
      diskPct: percent('disk_pct'),
      ramUsedBytes: bytes('ram_used_bytes'),
      ramTotalBytes: bytes('ram_total_bytes'),
      diskUsedBytes: bytes('disk_used_bytes'),
      diskTotalBytes: bytes('disk_total_bytes'),
      diskPath: value['disk_path'] as String,
      sampledAt: DateTime.parse(value['sampled_at'] as String).toUtc(),
      receivedAt: DateTime.parse(value['received_at'] as String).toUtc(),
    );
  }
}

class HostSnapshot {
  final String id;
  final String name;
  final String os;
  final AgentStatus status;
  final DateTime? lastSeenAt;
  final HostMetrics? metrics;

  const HostSnapshot({
    required this.id,
    required this.name,
    required this.os,
    required this.status,
    required this.lastSeenAt,
    required this.metrics,
  });

  factory HostSnapshot.fromJson(Map<String, dynamic> value) {
    final last = value['last_seen_at'];
    final latest = value['latest_metrics'];
    return HostSnapshot(
      id: value['id'] as String,
      name: value['name'] as String,
      os: value['os'] as String,
      status: parseAgentStatus(value['status'] as String),
      lastSeenAt: last == null ? null : DateTime.parse(last as String).toUtc(),
      metrics: latest == null
          ? null
          : HostMetrics.fromJson(Map<String, dynamic>.from(latest as Map)),
    );
  }
}

String humanBytes(int bytes) {
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  var value = bytes.toDouble();
  var unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return '${value.toStringAsFixed(unit == 0 ? 0 : 1)} ${units[unit]}';
}

String elapsedLabel(DateTime? date, DateTime now) {
  if (date == null) return 'No reports yet';
  final age = now.toUtc().difference(date.toUtc());
  if (age.isNegative || age.inSeconds < 10) return 'Just now';
  if (age.inMinutes < 1) return '${age.inSeconds}s ago';
  if (age.inHours < 1) return '${age.inMinutes}m ago';
  if (age.inDays < 1) return '${age.inHours}h ago';
  return '${age.inDays}d ago';
}
