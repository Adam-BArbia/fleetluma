// ignore_for_file: prefer_interpolation_to_compose_strings
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../data/fleet_api.dart';

// Authenticated historical samples. No synthetic/seeded chart values.
class HostHistoryPoint {
  final DateTime time;
  final double cpu;
  final double ram;
  final double disk;

  const HostHistoryPoint(this.time, this.cpu, this.ram, this.disk);

  factory HostHistoryPoint.fromJson(Map<String, dynamic> value) {
    double percent(String key) {
      final item = value[key];
      if (item is! num) throw const FormatException('Invalid history sample');
      final pct = item.toDouble();
      if (!pct.isFinite || pct < 0 || pct > 100) {
        throw const FormatException('Invalid history percentage');
      }
      return pct;
    }
    final time = DateTime.parse(value['received_at'] as String).toUtc();
    return HostHistoryPoint(
      time, percent('cpu_pct'), percent('ram_pct'), percent('disk_pct'));
  }
}

Duration historyWindow(String window) => switch (window) {
  '15m' => const Duration(minutes: 15),
  '1h' => const Duration(hours: 1),
  '24h' => const Duration(hours: 24),
  _ => throw const FormatException('Unsupported history window'),
};

Future<List<HostHistoryPoint>> fetchHostHistory(
  HttpFleetApi api,
  String hostId,
  String window, {
  http.Client? client,
}) async {
  historyWindow(window); // Reject invalid windows before any HTTP call.
  final jwt = await api.tokenProvider?.call();
  if (api.tokenProvider != null && (jwt == null || jwt.isEmpty)) {
    throw const FleetSessionExpiredException();
  }
  final endpoint = api.baseUri.replace(
    pathSegments: [
      ...api.baseUri.pathSegments.where((part) => part.isNotEmpty),
      'api', 'v1', 'hosts', hostId, 'history',
    ],
    queryParameters: {'window': window},
  );
  final owned = client == null;
  final httpClient = client ?? http.Client();
  try {
    final response = await httpClient.get(endpoint, headers: {
      'Accept': 'application/json',
      if (jwt != null && jwt.isNotEmpty) 'Authorization': 'Bearer $jwt',
    }).timeout(const Duration(seconds: 8));
    if (response.statusCode == 401) {
      throw const FleetSessionExpiredException();
    }
    if (response.statusCode == 403 || response.statusCode == 404) {
      throw const FleetAccessDeniedException();
    }
    if (response.statusCode != 200) {
      throw FleetConnectionException(
          'History temporarily unavailable (HTTP ' +
          response.statusCode.toString() + ').');
    }
    final body = jsonDecode(response.body);
    if (body is! Map || body['items'] is! List) {
      throw const FormatException('Unexpected history response');
    }
    final points = <HostHistoryPoint>[];
    for (final item in body['items'] as List) {
      if (item is! Map) throw const FormatException('Invalid history entry');
      points.add(HostHistoryPoint.fromJson(Map<String, dynamic>.from(item)));
    }
    points.sort((a, b) => a.time.compareTo(b.time));
    return points;
  } on TimeoutException {
    throw const FleetConnectionException('History request timed out.');
  } on http.ClientException {
    throw const FleetConnectionException('History network unavailable.');
  } finally {
    if (owned) httpClient.close();
  }
}

class WebHostHistoryCharts extends StatefulWidget {
  final HttpFleetApi api;
  final String hostId;

  const WebHostHistoryCharts({
    super.key, required this.api, required this.hostId,
  });

  @override
  State<WebHostHistoryCharts> createState() => _WebHostHistoryChartsState();
}

class _WebHostHistoryChartsState extends State<WebHostHistoryCharts> {
  static const _teal = Color(0xFF55E5D3);
  static const _blue = Color(0xFF86A7FF);
  static const _amber = Color(0xFFF6BE69);
  static const _muted = Color(0xFFA1AFCA);

  String window = '15m';
  List<HostHistoryPoint> points = const [];
  Timer? refresher;
  bool loading = true;
  String? error;
  int generation = 0;
  DateTime? receivedAt;

  @override
  void initState() {
    super.initState();
    _load();
    // Dashboard host snapshot polls every five seconds. Historical charts
    // intentionally poll less often to avoid unnecessary 24-hour DB reads.
    refresher = Timer.periodic(
      const Duration(seconds: 30), (_) => _load());
  }

  @override
  void didUpdateWidget(covariant WebHostHistoryCharts oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.hostId != widget.hostId ||
        !identical(oldWidget.api, widget.api)) {
      points = const [];
      _load();
    }
  }

  @override
  void dispose() {
    refresher?.cancel();
    generation++;
    super.dispose();
  }

  Future<void> _load() async {
    final token = ++generation;
    if (mounted) setState(() { loading = true; });
    try {
      final result = await fetchHostHistory(widget.api, widget.hostId, window);
      if (!mounted || token != generation) return;
      setState(() {
        points = result;
        receivedAt = DateTime.now().toUtc();
        error = null;
        loading = false;
      });
    } catch (_) {
      if (!mounted || token != generation) return;
      setState(() {
        error = 'History unavailable. Latest readings remain above.';
        loading = false;
      });
    }
  }

  void _select(String next) {
    if (window == next) return;
    setState(() {
      window = next;
      points = const [];
      receivedAt = null;
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final finish = DateTime.now().toUtc();
    final start = finish.subtract(historyWindow(window));
    final visible = points.where(
      (p) => !p.time.isBefore(start) && !p.time.isAfter(finish),
    ).toList(growable: false);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SizedBox(height: 16),
      const Divider(color: Color(0xFF27374E)),
      const SizedBox(height: 10),
      Row(children: [
        const Expanded(child: Text('RESOURCE HISTORY',
          style: TextStyle(color: _muted, fontSize: 10,
            letterSpacing: 1.1, fontWeight: FontWeight.w800))),
        for (final option in const ['15m', '1h', '24h'])
          Padding(padding: const EdgeInsets.only(left: 5),
            child: InkWell(
              key: ValueKey('window-' + widget.hostId + '-' + option),
              onTap: () => _select(option),
              borderRadius: BorderRadius.circular(8),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: window == option
                    ? const Color(0xFF173D45)
                    : const Color(0xFF1A2639)),
                child: Text(option, style: TextStyle(
                  fontSize: 10, fontWeight: FontWeight.w700,
                  color: window == option ? _teal : _muted)),
              ),
            ),
          ),
      ]),
      const SizedBox(height: 9),
      if (error != null) Text(error!, style: const TextStyle(
          color: _amber, fontSize: 11)),
      if (visible.isEmpty && loading)
        const Padding(padding: EdgeInsets.symmetric(vertical: 25),
          child: Center(child: SizedBox(width: 18, height: 18,
            child: CircularProgressIndicator(strokeWidth: 2))))
      else if (visible.isEmpty)
        const Padding(padding: EdgeInsets.symmetric(vertical: 14),
          child: Text('No recorded samples in this time range',
            style: TextStyle(color: _muted, fontSize: 11)))
      else ...[
        _plotRow('CPU', _teal, visible, start, finish, (p) => p.cpu),
        const SizedBox(height: 8),
        _plotRow('RAM', _blue, visible, start, finish, (p) => p.ram),
        const SizedBox(height: 8),
        _plotRow('DISK', _amber, visible, start, finish, (p) => p.disk),
      ],
      const SizedBox(height: 5),
      Row(children: [
        Text(visible.length.toString() + ' recorded samples',
          style: const TextStyle(color: _muted, fontSize: 10)),
        const Spacer(),
        Text(receivedAt == null ? '' : 'Updated recently',
          style: const TextStyle(color: _muted, fontSize: 10)),
      ]),
    ]);
  }

  Widget _plotRow(
    String name, Color color, List<HostHistoryPoint> samples,
    DateTime start, DateTime finish,
    double Function(HostHistoryPoint) metric,
  ) => Row(children: [
    SizedBox(width: 38, child: Text(name, style: TextStyle(
      color: color, fontSize: 11, fontWeight: FontWeight.w800))),
    Expanded(child: SizedBox(height: 66,
      child: CustomPaint(
        painter: _MetricHistoryPainter(
          points: samples, begin: start, end: finish, color: color,
          extract: metric),
        child: const SizedBox.expand(),
      ),
    )),
    const SizedBox(width: 8),
    SizedBox(width: 46, child: Text(
      samples.isEmpty ? '—' :
        metric(samples.last).toStringAsFixed(1) + '%',
      textAlign: TextAlign.right,
      style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 11),
    )),
  ]);
}

// Canvas rendering avoids a new chart dependency, keeps the Android APK
// untouched, uses real timestamps, and breaks the line across reporting gaps.
class _MetricHistoryPainter extends CustomPainter {
  final List<HostHistoryPoint> points;
  final DateTime begin;
  final DateTime end;
  final Color color;
  final double Function(HostHistoryPoint) extract;

  const _MetricHistoryPainter({
    required this.points, required this.begin, required this.end,
    required this.color, required this.extract,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width < 2 || size.height < 2) return;
    const top = 7.0;
    const bottom = 6.0;
    final drawH = math.max(1.0, size.height - top - bottom);
    final grid = Paint()..color = const Color(0xFF2B3B51)
      ..strokeWidth = 0.7;
    for (final fraction in const [0.0, 0.5, 1.0]) {
      final y = top + drawH * fraction;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }

    final durationMs = math.max(1, end.difference(begin).inMilliseconds);
    final pen = Paint()..color = color..strokeWidth = 1.9
      ..strokeCap = StrokeCap.round..style = PaintingStyle.stroke;
    final dot = Paint()..color = color..style = PaintingStyle.fill;

    Offset? previous;
    DateTime? lastTime;
    for (final sample in points) {
      final x = sample.time.difference(begin).inMilliseconds /
          durationMs * size.width;
      final y = top + (1 - extract(sample) / 100) * drawH;
      final current = Offset(x.clamp(0.0, size.width),
          y.clamp(top, top + drawH));
      // Do not visually connect samples separated by more than a minute.
      if (previous != null && lastTime != null &&
          sample.time.difference(lastTime).inSeconds <= 60) {
        canvas.drawLine(previous, current, pen);
      }
      previous = current;
      lastTime = sample.time;
    }
    if (previous != null) canvas.drawCircle(previous, 3.0, dot);
  }

  @override
  bool shouldRepaint(covariant _MetricHistoryPainter oldDelegate) =>
      !identical(oldDelegate.points, points) ||
      oldDelegate.begin != begin || oldDelegate.end != end ||
      oldDelegate.color != color;
}
