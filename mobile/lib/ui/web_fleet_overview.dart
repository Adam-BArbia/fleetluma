import 'package:flutter/material.dart';

import '../models/host_snapshot.dart';
import '../state/fleet_controller.dart';

// Web-only presentation dashboard. Uses the existing authenticated poller.
// Android continues to use FleetScreen without any layout changes.
const _bg = Color(0xFF080E1A);
const _panel = Color(0xFF111D30);
const _stroke = Color(0xFF27374E);
const _muted = Color(0xFFA1AFCA);
const _mint = Color(0xFF55E5D3);
const _blue = Color(0xFF86A7FF);
const _amber = Color(0xFFF6BE69);

class WebFleetOverview extends StatelessWidget {
  final FleetController state;
  final VoidCallback? onManageDevices;
  final Future<void> Function()? onSignOut;

  const WebFleetOverview({
    super.key,
    required this.state,
    this.onManageDevices,
    this.onSignOut,
  });

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 1000;
    final connected = state.hosts.where(
      (host) => host.status == AgentStatus.connected).toList();
    final stale = state.hosts.where(
      (host) => host.status == AgentStatus.stale).length;
    final reported = connected.where((host) => host.metrics != null).toList();

    double? avg(double Function(HostMetrics) metric) {
      if (reported.isEmpty) return null;
      return reported.map((host) => metric(host.metrics!))
          .reduce((a, b) => a + b) / reported.length;
    }

    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(child: Row(children: [
        if (wide) _sidebar(),
        Expanded(child: RefreshIndicator(
          onRefresh: state.refresh,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.all(wide ? 32 : 18),
            children: [
              Row(children: [
                if (!wide) ...[
                  const Icon(Icons.radar_rounded, color: _mint, size: 26),
                  const SizedBox(width: 10),
                ],
                const Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Fleet command center', style: TextStyle(
                      fontSize: 26, fontWeight: FontWeight.w800)),
                    SizedBox(height: 5),
                    Text('Real infrastructure health · Windows + Linux',
                      style: TextStyle(fontSize: 12, color: _muted)),
                  ],
                )),
                if (onManageDevices != null)
                  OutlinedButton.icon(
                    onPressed: onManageDevices,
                    icon: const Icon(Icons.add_rounded),
                    label: const Text('Pair device')),
                IconButton(
                  tooltip: 'Refresh',
                  onPressed: state.isRefreshing ? null : state.refresh,
                  icon: const Icon(Icons.refresh_rounded)),
                if (!wide && onSignOut != null)
                  IconButton(onPressed: () { onSignOut!(); },
                    tooltip: 'Sign out',
                    icon: const Icon(Icons.logout_rounded)),
              ]),
              const SizedBox(height: 16),
              Row(children: [
                const Icon(Icons.circle, size: 8, color: _mint),
                const SizedBox(width: 8),
                const Text('5-SECOND POLLING', style: TextStyle(
                  color: _mint, letterSpacing: 1.0, fontSize: 10,
                  fontWeight: FontWeight.w800)),
                const Spacer(),
                Flexible(child: Text(
                  state.lastRefreshAt == null ? 'Waiting for API'
                      : 'Updated ' + elapsedLabel(state.lastRefreshAt, DateTime.now()),
                  style: const TextStyle(color: _muted, fontSize: 11),
                  textAlign: TextAlign.right)),
              ]),
              if (state.errorMessage != null) ...[
                const SizedBox(height: 12),
                _panelWrap(
                  child: Row(children: [
                    const Icon(Icons.warning_amber_rounded, color: _amber),
                    const SizedBox(width: 12),
                    Expanded(child: Text(
                      'Connection issue. Showing last available readings. ' +
                          state.errorMessage!,
                      style: const TextStyle(fontSize: 12))),
                  ])),
              ],
              const SizedBox(height: 23),
              LayoutBuilder(builder: (context, box) {
                final columns = box.maxWidth >= 900 ? 4
                    : box.maxWidth >= 450 ? 2 : 1;
                final cardWidth = (box.maxWidth - (columns - 1) * 12) / columns;
                return Wrap(spacing: 12, runSpacing: 12, children: [
                  _statCard('TOTAL HOSTS', state.hosts.length.toString(),
                      Icons.dns_rounded, _blue, cardWidth),
                  _statCard('CONNECTED', connected.length.toString(),
                      Icons.wifi_tethering_rounded, _mint, cardWidth),
                  _statCard('STALE', stale.toString(),
                      Icons.schedule_rounded, _amber, cardWidth),
                  _statCard('REPORTING', reported.length.toString(),
                      Icons.ssid_chart_rounded, _blue, cardWidth),
                ]);
              }),
              const SizedBox(height: 22),
              _panelWrap(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Resource utilization', style: TextStyle(
                    fontWeight: FontWeight.w800, fontSize: 18)),
                  const SizedBox(height: 5),
                  Text(reported.isEmpty
                    ? 'Waiting for a connected agent to send metrics'
                    : 'Fleet averages from ' + reported.length.toString() +
                        ' connected host(s)',
                    style: const TextStyle(color: _muted, fontSize: 11)),
                  const SizedBox(height: 20),
                  LayoutBuilder(builder: (context, box) {
                    final metrics = <Widget>[
                      _summaryMetric('CPU load', avg((m) => m.cpuPct), _mint),
                      _summaryMetric('Memory use', avg((m) => m.ramPct), _blue),
                      _summaryMetric('Disk use', avg((m) => m.diskPct), _amber),
                    ];
                    if (box.maxWidth < 580) {
                      return Column(children: [
                        for (final metric in metrics) ...[
                          metric, const SizedBox(height: 16),
                        ],
                      ]);
                    }
                    return Row(children: [
                      for (var i = 0; i < metrics.length; i++) ...[
                        if (i != 0) const SizedBox(width: 23),
                        Expanded(child: metrics[i]),
                      ],
                    ]);
                  }),
                ])),
              const SizedBox(height: 25),
              Row(children: [
                const Text('Monitored machines', style: TextStyle(
                  fontSize: 18, fontWeight: FontWeight.w800)),
                const Spacer(),
                Text(state.hosts.length.toString() + ' devices',
                  style: const TextStyle(color: _muted, fontSize: 11)),
              ]),
              const SizedBox(height: 12),
              if (state.loading && !state.hasLoadedOnce)
                const Padding(padding: EdgeInsets.all(48),
                  child: Center(child: CircularProgressIndicator()))
              else if (state.hosts.isEmpty)
                _panelWrap(child: const Text(
                  'No connected devices yet. Install an agent and pair it.',
                  style: TextStyle(color: _muted)))
              else LayoutBuilder(builder: (context, box) {
                final columns = box.maxWidth >= 900 ? 2 : 1;
                final cardWidth = (box.maxWidth - (columns - 1) * 12) / columns;
                return Wrap(spacing: 12, runSpacing: 12, children: [
                  for (final host in state.hosts)
                    SizedBox(width: cardWidth, child: _hostCard(host)),
                ]);
              }),
              const SizedBox(height: 20),
              const Text(
                'STALE / REVOKED metrics are last-known readings, not live. '
                'Fleet averages exclude hosts without connected readings.',
                style: TextStyle(color: _muted, fontSize: 11, height: 1.5)),
            ],
          ),
        )),
      ])),
    );
  }

  Widget _sidebar() => Container(
    width: 230,
    padding: const EdgeInsets.fromLTRB(22, 30, 22, 18),
    decoration: const BoxDecoration(
      color: Color(0xFF0D1525),
      border: Border(right: BorderSide(color: _stroke))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Row(children: [
        Icon(Icons.radar_rounded, color: _mint, size: 28),
        SizedBox(width: 10),
        Text('FleetLuma', style: TextStyle(
          fontSize: 20, fontWeight: FontWeight.w900)),
      ]),
      const SizedBox(height: 8),
      const Text('INFRASTRUCTURE MONITOR', style: TextStyle(
        color: _muted, fontSize: 10, letterSpacing: 1)),
      const SizedBox(height: 40),
      _nav(Icons.space_dashboard_rounded, 'Overview', null, true),
      _nav(Icons.devices_rounded, 'Manage devices', onManageDevices, false),
      const Spacer(),
      _panelWrap(child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(Icons.cloud_done_rounded, color: _mint),
          SizedBox(height: 8),
          Text('Cloud coordinator', style: TextStyle(
            fontWeight: FontWeight.w700)),
          Text('Authenticated REST', style: TextStyle(
            fontSize: 11, color: _muted)),
        ])),
      const SizedBox(height: 16),
      if (onSignOut != null)
        _nav(Icons.logout_rounded, 'Sign out',
          () { onSignOut!(); }, false),
    ]),
  );

  Widget _nav(IconData icon, String title, VoidCallback? tap, bool active) =>
    Material(color: active ? const Color(0xFF15343E) : Colors.transparent,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(onTap: tap,
        child: Padding(padding: const EdgeInsets.all(14),
          child: Row(children: [
            Icon(icon, color: active ? _mint : _muted, size: 20),
            const SizedBox(width: 12),
            Text(title, style: TextStyle(
              color: active ? Colors.white : _muted,
              fontWeight: active ? FontWeight.w800 : FontWeight.w500)),
          ]))));

  Widget _panelWrap({required Widget child}) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: _panel, borderRadius: BorderRadius.circular(17),
      border: Border.all(color: _stroke)),
    child: child,
  );

  Widget _statCard(String label, String value, IconData icon, Color tone,
      double width) => SizedBox(width: width, child: _panelWrap(
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(label, style: const TextStyle(
          color: _muted, fontSize: 10, fontWeight: FontWeight.w800))),
        Icon(icon, color: tone, size: 19),
      ]),
      const SizedBox(height: 14),
      Text(value, style: TextStyle(
        color: tone, fontSize: 30, fontWeight: FontWeight.w900)),
    ]),
  ));

  Widget _bar(double? pct, Color tone) => ClipRRect(
    borderRadius: BorderRadius.circular(8),
    child: LinearProgressIndicator(
      value: ((pct ?? 0) / 100).clamp(0.0, 1.0),
      minHeight: 8, color: tone,
      backgroundColor: const Color(0xFF26384C),
    ));

  Widget _summaryMetric(String title, double? pct, Color tone) => Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(title, style: const TextStyle(color: _muted))),
        Text(pct == null ? '—' : pct.toStringAsFixed(1) + '%',
          style: TextStyle(color: tone, fontSize: 20,
            fontWeight: FontWeight.w800)),
      ]),
      const SizedBox(height: 10),
      _bar(pct, tone),
    ]);

  Widget _hostCard(HostSnapshot host) {
    final live = host.status == AgentStatus.connected;
    final tone = switch (host.status) {
      AgentStatus.connected => _mint,
      AgentStatus.pending => _muted,
      AgentStatus.stale => _amber,
      AgentStatus.revoked => const Color(0xFFFF8D95),
    };
    final m = host.metrics;
    return _panelWrap(child: Column(
      crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.computer_rounded, color: tone, size: 25),
          const SizedBox(width: 12),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(host.name, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w800,
                    fontSize: 17)),
              const SizedBox(height: 4),
              Text(host.os.toUpperCase() + ' · ' +
                  elapsedLabel(host.lastSeenAt, DateTime.now()),
                style: const TextStyle(color: _muted, fontSize: 11)),
            ])),
          Text(host.status.name.toUpperCase(), style: TextStyle(
            color: tone, fontWeight: FontWeight.w800, fontSize: 10)),
        ]),
        const SizedBox(height: 18),
        if (m == null)
          const Text('Awaiting first metric sample',
            style: TextStyle(color: _muted))
        else ...[
          if (!live) ...[
            const Text('LAST-KNOWN · NOT LIVE',
              style: TextStyle(color: _amber, fontSize: 10)),
            const SizedBox(height: 10),
          ],
          _hostMetric('CPU', m.cpuPct, _mint),
          const SizedBox(height: 12),
          _hostMetric('RAM', m.ramPct, _blue),
          const SizedBox(height: 12),
          _hostMetric('DISK', m.diskPct, _amber),
          const SizedBox(height: 16),
          const Divider(color: _stroke),
          const SizedBox(height: 7),
          Text('RAM: ' + humanBytes(m.ramUsedBytes) + ' / ' +
                humanBytes(m.ramTotalBytes),
            style: const TextStyle(fontSize: 11, color: _muted)),
          const SizedBox(height: 4),
          Text('Disk: ' + humanBytes(m.diskUsedBytes) + ' / ' +
                humanBytes(m.diskTotalBytes),
            style: const TextStyle(fontSize: 11, color: _muted)),
          const SizedBox(height: 8),
          Text('Received ' + elapsedLabel(m.receivedAt, DateTime.now()),
            style: const TextStyle(fontSize: 10, color: _muted)),
        ],
      ],
    ));
  }

  Widget _hostMetric(String label, double pct, Color tone) => Row(children: [
    SizedBox(width: 43, child: Text(label,
      style: const TextStyle(fontSize: 11, color: _muted))),
    Expanded(child: _bar(pct, tone)),
    const SizedBox(width: 10),
    SizedBox(width: 53, child: Text(pct.toStringAsFixed(1) + '%',
      textAlign: TextAlign.right,
      style: TextStyle(color: tone, fontSize: 12,
        fontWeight: FontWeight.w700))),
  ]);
}
