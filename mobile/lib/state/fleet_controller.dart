import 'dart:async';

import 'package:flutter/foundation.dart';

import '../data/fleet_api.dart';
import '../models/host_snapshot.dart';

/// Owns the 5-second poll loop, previous readings, and failure state.
class FleetController extends ChangeNotifier {
  final FleetApi api;
  final Duration interval;

  FleetController({
    required this.api,
    this.interval = const Duration(seconds: 5),
  });

  Timer? _poller;
  bool _fetching = false;
  bool _disposed = false;
  bool loading = true;
  bool hasLoadedOnce = false;
  String? errorMessage;
  List<HostSnapshot> hosts = const [];
  DateTime? lastRefreshAt;

  bool get hasData => hosts.isNotEmpty;
  bool get isRefreshing => _fetching;

  void start() {
    if (_disposed || _poller != null) return;
    refresh();
    _poller = Timer.periodic(interval, (_) => refresh());
  }

  void stop() {
    _poller?.cancel();
    _poller = null;
  }

  Future<void> refresh() async {
    if (_disposed || _fetching) return;
    _fetching = true;
    if (!hasLoadedOnce) loading = true;
    _notify();
    try {
      final received = await api.fetchHosts();
      if (_disposed) return;
      hosts = received;
      errorMessage = null;
      hasLoadedOnce = true;
      lastRefreshAt = DateTime.now().toUtc();
    } catch (error) {
      if (_disposed) return;
      errorMessage = error.toString();
    } finally {
      _fetching = false;
      loading = false;
      _notify();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    stop();
    _disposed = true;
    super.dispose();
  }
}
