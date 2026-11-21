import 'package:flutter/material.dart';

import '../models/host_snapshot.dart';
import '../state/fleet_controller.dart';

const _mint = Color(0xFF55E5D3);
const _navyCard = Color(0xFF151F34);
const _subtle = Color(0xFFA1AFCA);
const _amber = Color(0xFFF6BE69);

class FleetScreen extends StatefulWidget {
  final FleetController controller;
  final String apiUrl;
  final Future<void> Function()? onSignOut;
  final VoidCallback? onManageDevices;

  const FleetScreen({
    super.key,
    required this.controller,
    required this.apiUrl,
    this.onSignOut,
    this.onManageDevices,
  });

  @override
  State<FleetScreen> createState() => _FleetScreenState();
}

class _FleetScreenState extends State<FleetScreen>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.controller.start();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      widget.controller.start();
    } else {
      widget.controller.stop();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final state = widget.controller;
        return Scaffold(
          appBar: AppBar(
            title: const Row(children: [
              Icon(Icons.radar_rounded, color: _mint),
              SizedBox(width: 10),
              Text('FleetLuma', style: TextStyle(fontWeight: FontWeight.w800)),
            ]),
            actions: [
              if (widget.onManageDevices != null)
                IconButton(
                  tooltip: 'Manage devices',
                  onPressed: widget.onManageDevices,
                  icon: const Icon(Icons.devices_other_rounded),
                ),
              if (widget.onSignOut != null)
                IconButton(
                  tooltip: 'Sign out',
                  onPressed: () { widget.onSignOut!.call(); },
                  icon: const Icon(Icons.logout_rounded),
                ),
              IconButton(
                tooltip: 'Refresh fleet',
                onPressed: state.isRefreshing ? null : state.refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: SafeArea(
            child: RefreshIndicator(
              onRefresh: state.refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 14,
                ),
                children: [
                  _sectionHeader(state),
                  const SizedBox(height: 20),
                  if (state.errorMessage != null) _errorBanner(state),
                  if (state.loading && !state.hasLoadedOnce)
                    const Padding(
                      padding: EdgeInsets.only(top: 80),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  else if (state.hosts.isEmpty)
                    _emptyContent(state)
                  else ...[
                    _fleetOverview(state.hosts),
                    const SizedBox(height: 24),
                    const Text('HOSTS',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 12,
                          letterSpacing: 2,
                          color: _subtle,
                        )),
                    const SizedBox(height: 12),
                    for (final host in state.hosts) ...[
                      HostCard(host: host),
                      const SizedBox(height: 12),
                    ],
                  ],
                  const SizedBox(height: 28),
                  _footer(state),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _sectionHeader(FleetController state) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Fleet overview',
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          const Text('Live infrastructure signals from your connected agents.',
              style: TextStyle(color: _subtle)),
          const SizedBox(height: 9),
          Text(
            state.lastRefreshAt == null
                ? 'Waiting for first successful refresh'
                : 'Last updated ${elapsedLabel(state.lastRefreshAt, DateTime.now())}',
            style: const TextStyle(fontSize: 12, color: _mint),
          ),
        ],
      );

  Widget _errorBanner(FleetController state) => Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF372B2A),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            const Icon(Icons.wifi_off_rounded, color: _amber),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                state.hasLoadedOnce
                    ? 'Connection lost. Showing the last received snapshot.\n${state.errorMessage}'
                    : state.errorMessage!,
                style: const TextStyle(fontSize: 13),
              ),
            ),
            IconButton(
              tooltip: 'Try again',
              onPressed: state.isRefreshing ? null : state.refresh,
              icon: const Icon(Icons.refresh_rounded),
            ),
          ],
        ),
      );

  Widget _emptyContent(FleetController state) => Padding(
        padding: const EdgeInsets.only(top: 65, bottom: 65),
        child: Column(
          children: [
            const Icon(Icons.dns_outlined, size: 60, color: _subtle),
            const SizedBox(height: 15),
            Text(
              state.errorMessage == null
                  ? 'No hosts registered yet'
                  : 'Unable to load the fleet',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 10),
            Text(
              state.errorMessage == null
                  ? (widget.onManageDevices == null
                      ? 'No monitoring agents are registered yet.'
                      : 'Install FleetLuma Agent, then select Manage devices to pair it.')
                  : 'Verify the backend is reachable from this phone or emulator.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: _subtle),
            ),
            const SizedBox(height: 15),
            OutlinedButton.icon(
              onPressed: state.isRefreshing ? null : state.refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );

  Widget _fleetOverview(List<HostSnapshot> hosts) {
    final connected =
        hosts.where((host) => host.status == AgentStatus.connected).length;
    final stale = hosts.where((host) => host.status == AgentStatus.stale).length;
    return Container(
      padding: const EdgeInsets.all(19),
      decoration: BoxDecoration(
        color: _navyCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('YOUR INFRASTRUCTURE',
              style: TextStyle(
                color: _subtle,
                fontSize: 11,
                fontWeight: FontWeight.w600,
                letterSpacing: 1.4,
              )),
          const SizedBox(height: 18),
          Row(
            children: [
              _summaryValue('${hosts.length}', 'Total hosts', Colors.white),
              _summaryValue('$connected', 'Connected', _mint),
              _summaryValue('$stale', 'Stale', _amber),
            ],
          ),
        ],
      ),
    );
  }

  Widget _summaryValue(String number, String title, Color color) => Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(number,
                style: TextStyle(
                  color: color,
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                )),
            const SizedBox(height: 3),
            Text(title, style: const TextStyle(color: _subtle, fontSize: 12)),
          ],
        ),
      );

  Widget _footer(FleetController state) => Text(
        'Coordinator: ${widget.apiUrl}\n'
        'Host connection states are based on agent reports. '
        'STALE does not prove that a machine is powered off.',
        style: const TextStyle(color: _subtle, fontSize: 11, height: 1.5),
      );
}

class HostCard extends StatelessWidget {
  final HostSnapshot host;
  const HostCard({super.key, required this.host});

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (host.status) {
      AgentStatus.connected => _mint,
      AgentStatus.pending => _subtle,
      AgentStatus.stale => _amber,
      AgentStatus.revoked => Colors.redAccent,
    };
    final label = switch (host.status) {
      AgentStatus.connected => 'CONNECTED',
      AgentStatus.pending => 'PENDING',
      AgentStatus.stale => 'STALE',
      AgentStatus.revoked => 'REVOKED',
    };
    final data = host.metrics;

    return Semantics(
      label: '${host.name} $label',
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: _navyCard,
          borderRadius: BorderRadius.circular(19),
          border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(11),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: Icon(Icons.dns_rounded, color: statusColor),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(host.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                          )),
                      const SizedBox(height: 3),
                      Text(
                        '${host.os.toUpperCase()} · ${elapsedLabel(host.lastSeenAt, DateTime.now())}',
                        style: const TextStyle(color: _subtle, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(label,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w800,
                        fontSize: 10,
                      )),
                ),
              ],
            ),
            const SizedBox(height: 18),
            if (data == null)
              const Text('Awaiting first metric sample',
                  style: TextStyle(color: _subtle))
            else ...[
              if (host.status != AgentStatus.connected) ...[
                const Text(
                  host.status == AgentStatus.revoked
                      ? 'REVOKED · HISTORICAL READINGS'
                      : 'LAST KNOWN READINGS · NOT LIVE',
                  style: TextStyle(
                    color: _amber,
                    fontWeight: FontWeight.w700,
                    fontSize: 10,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 12),
              ],
              Row(
                children: [
                  _metric('CPU', data.cpuPct, statusColor),
                  const SizedBox(width: 9),
                  _metric('RAM', data.ramPct, statusColor),
                  const SizedBox(width: 9),
                  _metric('DISK', data.diskPct, statusColor),
                ],
              ),
              const SizedBox(height: 13),
              Text(
                'RAM ${humanBytes(data.ramUsedBytes)} / ${humanBytes(data.ramTotalBytes)}  ·  '
                'Disk ${humanBytes(data.diskUsedBytes)} / ${humanBytes(data.diskTotalBytes)}',
                style: const TextStyle(color: _subtle, fontSize: 11),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _metric(String label, double percent, Color color) => Expanded(
        child: Container(
          padding: const EdgeInsets.all(9),
          decoration: BoxDecoration(
            color: const Color(0xFF10192B),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: const TextStyle(
                    fontSize: 10,
                    color: _subtle,
                    fontWeight: FontWeight.w700,
                  )),
              const SizedBox(height: 8),
              FittedBox(
                child: Text('${percent.toStringAsFixed(0)}%',
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 19,
                    )),
              ),
              const SizedBox(height: 9),
              ClipRRect(
                borderRadius: BorderRadius.circular(9),
                child: LinearProgressIndicator(
                  value: percent / 100,
                  minHeight: 4,
                  backgroundColor: Colors.white12,
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                ),
              ),
            ],
          ),
        ),
      );
}
