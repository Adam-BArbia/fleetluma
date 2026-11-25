// ignore_for_file: prefer_interpolation_to_compose_strings
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../data/fleet_api.dart';
import '../models/host_snapshot.dart';

class MonitoredService {
  final String id;
  final String name;
  final String hostname;
  final String status;
  final bool enabled;
  final DateTime? checkedAt;
  final double? latencyMs;

  const MonitoredService({
    required this.id, required this.name, required this.hostname,
    required this.status, required this.enabled,
    required this.checkedAt, required this.latencyMs,
  });

  factory MonitoredService.fromJson(Map<String, dynamic> json) {
    final url = Uri.parse(json['url'] as String);
    if (!url.hasAuthority) throw const FormatException('Invalid service URL');
    final status = json['status'] as String;
    if (!['HEALTHY', 'UNHEALTHY', 'UNKNOWN'].contains(status)) {
      throw const FormatException('Unknown service status');
    }
    final rawLatency = json['latency_ms'];
    final latency = rawLatency is num ? rawLatency.toDouble() : null;
    if (latency != null && (!latency.isFinite || latency < 0)) {
      throw const FormatException('Invalid service latency');
    }
    final rawChecked = json['checked_at'];
    return MonitoredService(
      id: json['id'] as String,
      name: json['name'] as String,
      // Hostname only; never expose URL credentials, path, or query in UI.
      hostname: url.host,
      enabled: json['enabled'] as bool,
      status: status,
      checkedAt: rawChecked == null ? null :
          DateTime.parse(rawChecked as String).toUtc(),
      latencyMs: latency,
    );
  }
}

class ServiceCheck {
  final DateTime checkedAt;
  final String status;
  final int? httpCode;
  final double? latencyMs;
  final String? failureKind;

  const ServiceCheck({
    required this.checkedAt, required this.status,
    required this.httpCode, required this.latencyMs,
    required this.failureKind,
  });

  factory ServiceCheck.fromJson(Map<String, dynamic> value) {
    final latency = value['latency_ms'];
    if (latency != null && (latency is! num ||
        !latency.toDouble().isFinite || latency < 0)) {
      throw const FormatException('Invalid check latency');
    }
    final status = value['status'] as String;
    if (!['HEALTHY', 'UNHEALTHY', 'UNKNOWN'].contains(status)) {
      throw const FormatException('Invalid check status');
    }
    return ServiceCheck(
      checkedAt: DateTime.parse(value['checked_at'] as String).toUtc(),
      status: status,
      httpCode: value['http_code'] as int?,
      latencyMs: latency == null ? null : (latency as num).toDouble(),
      failureKind: value['failure_kind'] as String?,
    );
  }
}

Future<Map<String, dynamic>> _serviceGet(HttpFleetApi api, Uri uri,
    {http.Client? client}) async {
  final jwt = await api.tokenProvider?.call();
  if (api.tokenProvider != null && (jwt == null || jwt.isEmpty)) {
    throw const FleetSessionExpiredException();
  }
  final owned = client == null;
  final transport = client ?? http.Client();
  try {
    final response = await transport.get(uri, headers: {
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
      throw const FleetConnectionException('Service monitoring unavailable.');
    }
    final payload = jsonDecode(response.body);
    if (payload is! Map) {
      throw const FormatException('Invalid service response');
    }
    return Map<String, dynamic>.from(payload);
  } on TimeoutException {
    throw const FleetConnectionException('Service monitoring request timed out.');
  } on http.ClientException {
    throw const FleetConnectionException('Service monitoring network unavailable.');
  } on FormatException {
    throw const FleetConnectionException('Invalid service monitoring response.');
  } on TypeError {
    throw const FleetConnectionException('Invalid service monitoring response.');
  } finally {
    if (owned) transport.close();
  }
}

Future<List<MonitoredService>> fetchWebServices(HttpFleetApi api,
    {http.Client? client}) async {
  final workspace = await api.workspaceIdProvider?.call();
  if (api.workspaceIdProvider != null &&
      (workspace == null || workspace.isEmpty)) {
    throw const FleetAccessDeniedException();
  }
  final uri = api.baseUri.replace(
    pathSegments: [
      ...api.baseUri.pathSegments.where((p) => p.isNotEmpty),
      'api', 'v1', 'services',
    ],
    queryParameters: workspace == null ? null : {'workspace_id': workspace},
  );
  final body = await _serviceGet(api, uri, client: client);
  final rows = body['items'];
  if (rows is! List) throw const FormatException('Expected service list');
  return rows.map((item) => MonitoredService.fromJson(
      Map<String, dynamic>.from(item as Map))).toList(growable: false);
}

Future<List<ServiceCheck>> fetchWebServiceChecks(
    HttpFleetApi api, String serviceId, String window,
    {http.Client? client}) async {
  if (!const ['15m', '1h', '24h'].contains(window)) {
    throw const FormatException('Unsupported check window');
  }
  final uri = api.baseUri.replace(
    pathSegments: [
      ...api.baseUri.pathSegments.where((p) => p.isNotEmpty),
      'api', 'v1', 'services', serviceId, 'checks',
    ],
    queryParameters: {'window': window},
  );
  final body = await _serviceGet(api, uri, client: client);
  final rows = body['items'];
  if (rows is! List) throw const FormatException('Expected service checks');
  return rows.map((item) => ServiceCheck.fromJson(
    Map<String, dynamic>.from(item as Map))).toList(growable: false);
}

class WebServiceHealthOverview extends StatefulWidget {
  final HttpFleetApi api;
  const WebServiceHealthOverview({super.key, required this.api});

  @override
  State<WebServiceHealthOverview> createState() =>
      _WebServiceHealthOverviewState();
}

class _WebServiceHealthOverviewState extends State<WebServiceHealthOverview> {
  Timer? _timer;
  int _generation = 0;
  bool _loading = true;
  String? _error;
  List<MonitoredService> _services = const [];

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _load());
  }

  @override
  void didUpdateWidget(covariant WebServiceHealthOverview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.api, widget.api)) _load();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _generation++;
    super.dispose();
  }

  Future<void> _load() async {
    final sequence = ++_generation;
    if (_services.isEmpty && mounted) setState(() => _loading = true);
    try {
      final values = await fetchWebServices(widget.api);
      if (!mounted || sequence != _generation) return;
      setState(() { _services = values; _error = null; _loading = false; });
    } catch (_) {
      if (!mounted || sequence != _generation) return;
      setState(() {
        _error = 'HTTP monitoring unavailable. Try refreshing.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF111D30),
        border: Border.all(color: const Color(0xFF27374E)),
        borderRadius: BorderRadius.circular(17),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(child: Text('HTTP SERVICE HEALTH',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800))),
          IconButton(tooltip: 'Refresh HTTP services',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded)),
        ]),
        const SizedBox(height: 4),
        const Text('Independent scheduled checks of approved HTTPS endpoints',
          style: TextStyle(fontSize: 11, color: Color(0xFFA1AFCA))),
        const SizedBox(height: 16),
        if (_loading && _services.isEmpty)
          const Center(child: CircularProgressIndicator(strokeWidth: 2)),
        if (_error != null) Text(_error!,
          style: const TextStyle(fontSize: 12, color: Color(0xFFF6BE69))),
        if (!_loading && _services.isEmpty && _error == null)
          const Text('No approved HTTP services are configured yet.',
            style: TextStyle(fontSize: 12, color: Color(0xFFA1AFCA))),
        for (final service in _services)
          _ServiceCard(key: ValueKey('service-' + service.id),
            api: widget.api, service: service),
      ]),
    );
  }
}

class _ServiceCard extends StatefulWidget {
  final HttpFleetApi api;
  final MonitoredService service;
  const _ServiceCard({super.key, required this.api, required this.service});

  @override
  State<_ServiceCard> createState() => _ServiceCardState();
}

class _ServiceCardState extends State<_ServiceCard> {
  String _window = '1h';
  List<ServiceCheck> _checks = const [];
  bool _loading = false;
  String? _error;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant _ServiceCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.service.id != widget.service.id ||
        oldWidget.service.checkedAt != widget.service.checkedAt ||
        !identical(oldWidget.api, widget.api)) {
      // Parent service polling supplies new check timestamps every minute.
      // Refresh only when a newer persisted check exists; keep API reads bounded.
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    super.dispose();
  }

  Future<void> _load() async {
    final sequence = ++_generation;
    if (mounted) setState(() => _loading = true);
    try {
      final checks = await fetchWebServiceChecks(
        widget.api, widget.service.id, _window);
      if (!mounted || sequence != _generation) return;
      setState(() { _checks = checks; _loading = false; _error = null; });
    } catch (_) {
      if (!mounted || sequence != _generation) return;
      setState(() {
        _loading = false;
        _error = 'Check history unavailable.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final service = widget.service;
    final validCheck = service.checkedAt != null &&
      DateTime.now().toUtc().difference(service.checkedAt!).inMinutes < 10;
    final status = !service.enabled ? 'DISABLED' :
        !validCheck ? 'UNKNOWN' : service.status;
    final color = switch (status) {
      'HEALTHY' => const Color(0xFF55E5D3),
      'UNHEALTHY' => const Color(0xFFFF8D95),
      _ => const Color(0xFFF6BE69),
    };
    final newest = _checks.isEmpty ? null : _checks.last;
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: ExpansionTile(
        initiallyExpanded: false,
        tilePadding: const EdgeInsets.symmetric(horizontal: 8),
        title: Text(service.name, style: const TextStyle(
          fontSize: 13, fontWeight: FontWeight.w700)),
        subtitle: Text(service.hostname + ' · ' +
          (service.checkedAt == null ? 'Never checked' :
            'Checked ' + elapsedLabel(service.checkedAt, DateTime.now())),
          style: const TextStyle(fontSize: 10, color: Color(0xFFA1AFCA))),
        trailing: Text(status, style: TextStyle(
          color: color, fontSize: 10, fontWeight: FontWeight.w800)),
        children: [
          Row(children: [
            for (final option in const ['15m', '1h', '24h'])
              TextButton(
                onPressed: () {
                  if (_window == option) return;
                  setState(() { _window = option; _checks = const []; });
                  _load();
                },
                child: Text(option,
                  style: TextStyle(color: _window == option ?
                      const Color(0xFF55E5D3) :
                      const Color(0xFFA1AFCA)))),
            const Spacer(),
            IconButton(tooltip: 'Refresh check history',
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh_rounded, size: 17)),
          ]),
          if (_loading)
            const LinearProgressIndicator(minHeight: 2),
          if (_error != null)
            Text(_error!, style: const TextStyle(
              fontSize: 11, color: Color(0xFFF6BE69))),
          if (_checks.isEmpty && !_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('No recorded HTTP checks for this window.',
                style: TextStyle(fontSize: 11, color: Color(0xFFA1AFCA))),
            ),
          if (newest != null) ...[
            Row(children: [
              Text(newest.httpCode == null ? 'No HTTP response' :
                'HTTP ' + newest.httpCode.toString(),
                style: const TextStyle(fontSize: 12)),
              const SizedBox(width: 15),
              Text(newest.latencyMs == null ? 'Latency unavailable' :
                newest.latencyMs!.toStringAsFixed(0) + ' ms',
                style: const TextStyle(fontSize: 12,
                  color: Color(0xFF86A7FF))),
              const Spacer(),
              Text(_checks.length.toString() + ' checks',
                style: const TextStyle(
                  fontSize: 10, color: Color(0xFFA1AFCA))),
            ]),
            const SizedBox(height: 12),
            SizedBox(height: 52,
              child: CustomPaint(
                painter: _LatencyPainter(_checks),
                child: const SizedBox.expand(),
              ),
            ),
            const SizedBox(height: 9),
            if (newest.failureKind != null &&
                newest.failureKind != 'none')
              Text('Latest failure: ' + newest.failureKind!,
                style: const TextStyle(
                  fontSize: 11, color: Color(0xFFF6BE69))),
          ],
        ],
      ),
    );
  }
}

class _LatencyPainter extends CustomPainter {
  final List<ServiceCheck> checks;
  const _LatencyPainter(this.checks);

  @override
  void paint(Canvas canvas, Size size) {
    final samples = checks.where((s) => s.latencyMs != null).toList();
    if (samples.isEmpty || size.width <= 0 || size.height <= 0) return;
    final first = checks.first.checkedAt.millisecondsSinceEpoch;
    final last = checks.last.checkedAt.millisecondsSinceEpoch;
    final span = last == first ? 1 : last - first;
    final maxLatency = samples.map((s) => s.latencyMs!).reduce(
      (a, b) => a > b ? a : b);
    final denominator = maxLatency == 0 ? 1.0 : maxLatency;
    final paint = Paint()
      ..color = const Color(0xFF86A7FF)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    // Only join adjacent valid samples. Missing results leave visible gaps.
    ServiceCheck? previous;
    for (final check in checks) {
      if (check.latencyMs == null) {
        previous = null;
        continue;
      }
      final x = (check.checkedAt.millisecondsSinceEpoch - first) /
          span * size.width;
      final y = size.height - check.latencyMs! / denominator *
          (size.height - 5) - 3;
      if (previous != null && previous.latencyMs != null) {
        final px = (previous.checkedAt.millisecondsSinceEpoch - first) /
            span * size.width;
        final py = size.height - previous.latencyMs! / denominator *
            (size.height - 5) - 3;
        canvas.drawLine(Offset(px, py), Offset(x, y), paint);
      } else {
        canvas.drawCircle(Offset(x, y), 2, Paint()
          ..color = const Color(0xFF86A7FF));
      }
      previous = check;
    }
  }

  @override
  bool shouldRepaint(covariant _LatencyPainter oldDelegate) =>
      !identical(oldDelegate.checks, checks);
}
