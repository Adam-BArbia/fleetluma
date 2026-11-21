import 'package:flutter/material.dart';

import '../data/device_api.dart';

/// Explicit human approval for a one-time pairing code. This is not agent auth.
class DeviceManagementScreen extends StatefulWidget {
  final FleetDeviceApi api;
  const DeviceManagementScreen({super.key, required this.api});

  @override
  State<DeviceManagementScreen> createState() => _DeviceManagementScreenState();
}

class _DeviceManagementScreenState extends State<DeviceManagementScreen> {
  final _code = TextEditingController();
  List<FleetWorkspace> _workspaces = const [];
  List<ManagedDevice> _devices = const [];
  String? _workspaceId;
  PairingPreview? _preview;
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _perform(Future<void> Function() action) async {
    if (_busy) return;
    setState(() { _busy = true; _error = null; });
    try {
      await action();
    } catch (_) {
      // No raw HTTP response, JWT, device_code, or credential in UI messages.
      if (mounted) setState(() {
        _error = 'The action could not be completed. Check your access, code, or connection.';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _load() => _perform(() async {
    final workspaces = await widget.api.workspaces();
    if (!mounted) return;
    final allowed = workspaces.where((w) => w.canManage).toList();
    final selected = allowed.any((w) => w.id == _workspaceId)
        ? _workspaceId : (allowed.isNotEmpty ? allowed.first.id : null);
    setState(() { _workspaces = workspaces; _workspaceId = selected; });
    if (selected != null) {
      final devices = await widget.api.hosts(selected);
      if (mounted) setState(() => _devices = devices);
    } else {
      if (mounted) setState(() => _devices = const []);
    }
  });

  Future<void> _resolve() => _perform(() async {
    final code = _code.text.trim().toUpperCase();
    if (!RegExp(r'^[A-HJ-NP-Z2-9]{4}-?[A-HJ-NP-Z2-9]{4}$').hasMatch(code)) {
      if (mounted) setState(() => _error = 'Enter the eight-character code shown on the agent.');
      return;
    }
    final result = await widget.api.resolveCode(code);
    if (mounted) setState(() => _preview = result);
  });

  Future<void> _approve() => _perform(() async {
    final preview = _preview;
    final selected = _workspaceId;
    if (preview == null || selected == null) return;
    await widget.api.approve(preview.pairingId, selected);
    final updated = await widget.api.hosts(selected);
    if (!mounted) return;
    setState(() { _preview = null; _devices = updated; _code.clear(); });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Device approved. Waiting for its first report.')),
    );
  });

  Future<void> _deny() => _perform(() async {
    final preview = _preview;
    if (preview == null) return;
    await widget.api.deny(preview.pairingId);
    if (mounted) setState(() { _preview = null; _code.clear(); });
  });

  Future<void> _changeWorkspace(String? id) => _perform(() async {
    if (id == null) return;
    final devices = await widget.api.hosts(id);
    if (mounted) setState(() { _workspaceId = id; _devices = devices; _preview = null; });
  });

  Future<void> _confirmRevoke(ManagedDevice device) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Revoke device?'),
        content: Text(
          'Revoke ${device.name}? Its agent will no longer be allowed to report. '
          'The device will require new pairing to reconnect.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
                     child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true),
                       child: const Text('Revoke')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _perform(() async {
      await widget.api.revoke(device.id);
      final selected = _workspaceId;
      if (selected == null) return;
      final devices = await widget.api.hosts(selected);
      if (mounted) setState(() => _devices = devices);
    });
  }

  @override
  Widget build(BuildContext context) {
    final manageable = _workspaces.where((w) => w.canManage).toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Manage devices'),
        actions: [
          IconButton(
            tooltip: 'Refresh devices',
            onPressed: _busy ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 780),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Text('Pair a new computer',
                  style: TextStyle(fontSize: 23, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                const Text(
                  'Install FleetLuma Agent on the computer. Open its setup '
                  'window and enter the one-time code shown there. '
                  'Confirm the device before approving.',
                ),
                const SizedBox(height: 20),
                if (_busy) const LinearProgressIndicator(),
                if (_error != null) Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(_error!, style: const TextStyle(color: Colors.orangeAccent)),
                ),
                if (manageable.isEmpty) const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('Your account has no workspace administrator permission.'),
                  ),
                ) else ...[
                  DropdownButtonFormField<String>(
                    key: ValueKey('workspace-$_workspaceId'),
                    initialValue: _workspaceId,
                    decoration: const InputDecoration(labelText: 'Workspace'),
                    items: manageable.map((w) => DropdownMenuItem(
                      value: w.id, child: Text(w.name),
                    )).toList(),
                    onChanged: _busy ? null : _changeWorkspace,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _code,
                    enabled: !_busy && _preview == null,
                    textCapitalization: TextCapitalization.characters,
                    textInputAction: TextInputAction.done,
                    maxLength: 9,
                    decoration: const InputDecoration(
                      labelText: 'One-time pairing code',
                      hintText: 'ABCD-7294',
                      prefixIcon: Icon(Icons.password),
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 6),
                  FilledButton.icon(
                    onPressed: _busy || _preview != null ? null : _resolve,
                    icon: const Icon(Icons.search),
                    label: const Text('Review device'),
                  ),
                ],
                if (_preview != null) ...[
                  const SizedBox(height: 24),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Confirm this device',
                            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                          const SizedBox(height: 14),
                          Text('Computer: ${_preview!.hostname}'),
                          Text('Platform: ${_preview!.platform}'),
                          Text('Agent version: ${_preview!.agentVersion}'),
                          Text('Permissions: ${_preview!.capabilities.join(', ')}'),
                          Text('Code expires: ${_preview!.expiresAt.toLocal()}'),
                          const SizedBox(height: 12),
                          const Text('Approve only if you are physically setting up '
                              'this computer and the displayed code matches.',
                              style: TextStyle(color: Colors.amberAccent)),
                          const SizedBox(height: 16),
                          Wrap(spacing: 10, runSpacing: 10, children: [
                            OutlinedButton(
                              onPressed: _busy ? null : _deny,
                              child: const Text('Deny'),
                            ),
                            FilledButton(
                              onPressed: _busy ? null : _approve,
                              child: const Text('Approve and connect'),
                            ),
                          ]),
                        ],
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 32),
                const Text('Registered devices',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                if (_devices.isEmpty)
                  const Text('No devices in the selected workspace.')
                else
                  ..._devices.map((device) => Card(
                    child: ListTile(
                      leading: Icon(device.os == 'windows'
                          ? Icons.desktop_windows : Icons.computer),
                      title: Text(device.name),
                      subtitle: Text('${device.os} · ${device.status}'),
                      trailing: device.lifecycle == 'REVOKED'
                          ? const Text('Revoked')
                          : IconButton(
                              tooltip: 'Revoke ${device.name}',
                              icon: const Icon(Icons.block),
                              onPressed: _busy ? null : () => _confirmRevoke(device),
                            ),
                    ),
                  )),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
