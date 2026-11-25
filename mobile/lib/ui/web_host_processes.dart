// ignore_for_file: prefer_interpolation_to_compose_strings
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../data/fleet_api.dart';
import '../models/host_snapshot.dart';

class MonitoredProcess {
  final int pid;
  final String name;
  final double cpuPct;
  final int memoryBytes;

  const MonitoredProcess({
    required this.pid, required this.name,
    required this.cpuPct, required this.memoryBytes,
  });

  factory MonitoredProcess.fromJson(Map<String, dynamic> value) {
    final pid = value['pid'];
    final cpu = value['cpu_pct'];
    final memory = value['memory_bytes'];
    final name = value['name'];
    if (pid is! int || pid < 0 || cpu is! num ||
        !cpu.toDouble().isFinite || cpu < 0 ||
        memory is! int || memory < 0 ||
        name is! String || name.isEmpty) {
      throw const FormatException('Invalid process snapshot');
    }
    return MonitoredProcess(
      pid: pid, name: name, cpuPct: cpu.toDouble(),
      memoryBytes: memory,
    );
  }
}

class ProcessSnapshot {
  final DateTime? capturedAt;
  final List<MonitoredProcess> processes;
  const ProcessSnapshot(this.capturedAt, this.processes);

  factory ProcessSnapshot.fromJson(Map<String, dynamic> value) {
    final rows = value['processes'];
    if (rows is! List || rows.length > 10) {
      throw const FormatException('Unexpected process list');
    }
    final timestamp = value['captured_at'];
    if (timestamp != null && timestamp is! String) {
      throw const FormatException('Invalid snapshot timestamp');
    }
    return ProcessSnapshot(
      timestamp == null ? null : DateTime.parse(timestamp).toUtc(),
      rows.map((item) => MonitoredProcess.fromJson(
        Map<String, dynamic>.from(item as Map))).toList(growable: false),
    );
  }
}

Future<ProcessSnapshot> fetchWebProcesses(
  HttpFleetApi api, String hostId, {http.Client? client}
) async {
  final token = await api.tokenProvider?.call();
  if (api.tokenProvider != null && (token == null || token.isEmpty)) {
    throw const FleetSessionExpiredException();
  }
  final uri = api.baseUri.replace(pathSegments: [
    ...api.baseUri.pathSegments.where((s) => s.isNotEmpty),
    'api', 'v1', 'hosts', hostId, 'processes',
  ]);
  final owned = client == null;
  final transport = client ?? http.Client();
  try {
    final response = await transport.get(uri, headers: {
      'Accept': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    }).timeout(const Duration(seconds: 8));
    if (response.statusCode == 401) {
      throw const FleetSessionExpiredException();
    }
    if (response.statusCode == 403 || response.statusCode == 404) {
      throw const FleetAccessDeniedException();
    }
    if (response.statusCode != 200) {
      throw const FleetConnectionException('Process data unavailable.');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map) {
      throw const FormatException('Invalid process response');
    }
    return ProcessSnapshot.fromJson(Map<String, dynamic>.from(decoded));
  } on TimeoutException {
    throw const FleetConnectionException('Process request timed out.');
  } on http.ClientException {
    throw const FleetConnectionException('Process network unavailable.');
  } on FormatException {
    throw const FleetConnectionException('Invalid process response.');
  } on TypeError {
    throw const FleetConnectionException('Invalid process response.');
  } finally {
    if (owned) transport.close();
  }
}

/// Web-only, read-only process snapshot explorer. Android UI is unchanged.
class WebHostProcesses extends StatefulWidget {
  final HttpFleetApi api;
  final String hostId;
  const WebHostProcesses({super.key, required this.api, required this.hostId});

  @override
  State<WebHostProcesses> createState() => _WebHostProcessesState();
}

class _WebHostProcessesState extends State<WebHostProcesses> {
  Timer? _timer;
  int _generation = 0;
  ProcessSnapshot? _snapshot;
  bool _loading = true;
  bool _memorySort = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _load());
  }

  @override
  void didUpdateWidget(covariant WebHostProcesses oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.hostId != widget.hostId ||
        !identical(oldWidget.api, widget.api)) {
      _snapshot = null;
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final generation = ++_generation;
    if (mounted && _snapshot == null) setState(() => _loading = true);
    try {
      final value = await fetchWebProcesses(widget.api, widget.hostId);
      if (!mounted || generation != _generation) return;
      setState(() {
        _snapshot = value;
        _error = null;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _loading = false;
        _snapshot = null;
        _error = 'Process snapshot unavailable. Retry later.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final snapshot = _snapshot;
    final now = DateTime.now().toUtc();
    final age = snapshot?.capturedAt == null
      ? null : now.difference(snapshot!.capturedAt!);
    final isStale = age == null || age.isNegative ||
        age > const Duration(seconds: 90);
    final entries = [...?snapshot?.processes]
      ..sort((a, b) => _memorySort
        ? b.memoryBytes.compareTo(a.memoryBytes)
        : b.cpuPct.compareTo(a.cpuPct));

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SizedBox(height: 16),
      const Divider(color: Color(0xFF27374E)),
      const SizedBox(height: 8),
      ExpansionTile(
        key: ValueKey('processes-' + widget.hostId),
        tilePadding: EdgeInsets.zero,
        childrenPadding: EdgeInsets.zero,
        title: const Text('TOP 10 PROCESSES', style: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1.0)),
        subtitle: Text(
          snapshot?.capturedAt == null ? 'No snapshot received'
            : 'Captured ' + elapsedLabel(snapshot!.capturedAt, now) +
                (isStale ? ' · STALE SNAPSHOT' : ' · recent snapshot'),
          style: TextStyle(fontSize: 10,
            color: isStale ? const Color(0xFFF6BE69) :
                const Color(0xFFA1AFCA)),
        ),
        children: [
          Row(children: [
            TextButton(
              onPressed: () => setState(() => _memorySort = false),
              child: Text('CPU', style: TextStyle(
                color: !_memorySort ? const Color(0xFF55E5D3) :
                    const Color(0xFFA1AFCA))),
            ),
            TextButton(
              onPressed: () => setState(() => _memorySort = true),
              child: Text('Memory', style: TextStyle(
                color: _memorySort ? const Color(0xFF55E5D3) :
                    const Color(0xFFA1AFCA))),
            ),
            const Spacer(),
            IconButton(
              tooltip: 'Refresh processes',
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh_rounded, size: 17),
            ),
          ]),
          if (_loading && snapshot == null)
            const Padding(
              padding: EdgeInsets.all(12),
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(_error!, style: const TextStyle(
                  color: Color(0xFFF6BE69), fontSize: 11)),
            ),
          if (!_loading && entries.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('No process samples recorded yet',
                style: TextStyle(color: Color(0xFFA1AFCA), fontSize: 11)),
            ),
          for (final process in entries)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(children: [
                Expanded(child: Tooltip(
                  message: process.name,
                  child: Text(process.name, maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 11)))),
                const SizedBox(width: 8),
                SizedBox(width: 58, child: Text('PID ' +
                  process.pid.toString(), textAlign: TextAlign.right,
                  style: const TextStyle(
                    color: Color(0xFFA1AFCA), fontSize: 10))),
                const SizedBox(width: 8),
                SizedBox(width: 65, child: Text(
                  process.cpuPct.toStringAsFixed(1) + '% CPU',
                  textAlign: TextAlign.right,
                  style: const TextStyle(fontSize: 10))),
                const SizedBox(width: 9),
                SizedBox(width: 78, child: Text(
                  humanBytes(process.memoryBytes),
                  textAlign: TextAlign.right,
                  style: const TextStyle(
                    color: Color(0xFF86A7FF), fontSize: 10))),
              ]),
            ),
          const SizedBox(height: 6),
          const Text('Read-only snapshot; process usage is not continuous.',
            style: TextStyle(color: Color(0xFFA1AFCA), fontSize: 10)),
        ],
      ),
    ]);
  }
}
