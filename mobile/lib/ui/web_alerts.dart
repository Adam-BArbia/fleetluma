// ignore_for_file: prefer_interpolation_to_compose_strings
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../data/fleet_api.dart';
import '../models/host_snapshot.dart';

Future<Map<String,dynamic>> alertRequest(
  HttpFleetApi api, String method, List<String> segments,
  {Map<String,String>? query, Map<String,dynamic>? body,
   http.Client? client}
) async {
  final jwt = await api.tokenProvider?.call();
  if(jwt == null || jwt.isEmpty) {
    throw const FleetSessionExpiredException();
  }
  final url = api.baseUri.replace(
    pathSegments:[
      ...api.baseUri.pathSegments.where((s) => s.isNotEmpty),
      'api','v1','alerts',...segments,
    ], queryParameters:query);
  final owned = client == null;
  final transport = client ?? http.Client();
  try {
    final request = http.Request(method,url);
    request.headers['Accept']='application/json';
    request.headers['Authorization']='Bearer ' + jwt;
    if(body != null) {
      request.headers['Content-Type']='application/json';
      request.body=jsonEncode(body);
    }
    final response = await http.Response.fromStream(
      await transport.send(request).timeout(const Duration(seconds:8)));
    if(response.statusCode == 401) {
      throw const FleetSessionExpiredException();
    }
    if(response.statusCode == 403 || response.statusCode == 404) {
      throw const FleetAccessDeniedException();
    }
    if(response.statusCode < 200 || response.statusCode >= 300) {
      throw FleetConnectionException('Alert request failed (HTTP ' +
        response.statusCode.toString() + ').');
    }
    if(response.body.isEmpty)return {};
    final data = jsonDecode(response.body);
    if(data is! Map)throw const FormatException('Invalid alert response');
    return Map<String,dynamic>.from(data);
  } on TimeoutException {
    throw const FleetConnectionException('Alert request timed out.');
  } on http.ClientException {
    throw const FleetConnectionException('Alert service network unavailable.');
  } finally {
    if(owned)transport.close();
  }
}

Future<String> alertWorkspace(HttpFleetApi api) async {
  final value = await api.workspaceIdProvider?.call();
  if(value == null || value.isEmpty)throw const FleetAccessDeniedException();
  return value;
}

Future<List<Map<String,dynamic>>> fetchAlertCollection(
  HttpFleetApi api, String collection, {http.Client? client}
) async {
  if(collection != 'rules' && collection != 'incidents') {
    throw const FormatException('Unknown alert collection');
  }
  final workspace = await alertWorkspace(api);
  final value = await alertRequest(api,'GET',[collection],
    query:{'workspace_id':workspace},client:client);
  final rows = value['items'];
  if(rows is! List)throw const FormatException('Invalid alert collection');
  return rows.map((row) =>
    Map<String,dynamic>.from(row as Map)).toList(growable:false);
}

/// Web-only management surface. Read/write authorization is server enforced.
/// The panel is not included unless FLEETLUMA_ALERTS_UI_ENABLED=true.
class WebAlertsPanel extends StatefulWidget {
  final HttpFleetApi api;
  final List<HostSnapshot> hosts;
  const WebAlertsPanel({super.key,required this.api,required this.hosts});

  @override
  State<WebAlertsPanel> createState() => _WebAlertsPanelState();
}

class _WebAlertsPanelState extends State<WebAlertsPanel> {
  final _threshold = TextEditingController(text:'85');
  Timer? _poller;
  int _generation=0;
  String? _error;
  bool _busy=false;
  bool _loading=true;
  String? _hostId;
  String _metric='cpu_pct';
  List<Map<String,dynamic>> _rules=const [];
  List<Map<String,dynamic>> _incidents=const [];

  @override
  void initState() {
    super.initState();
    _load();
    _poller=Timer.periodic(const Duration(seconds:30),(_) => _load());
  }

  @override
  void dispose() {
    _generation++;
    _poller?.cancel();
    _threshold.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final generation=++_generation;
    try {
      final data = await Future.wait([
        fetchAlertCollection(widget.api,'rules'),
        fetchAlertCollection(widget.api,'incidents'),
      ]);
      if(!mounted || generation != _generation)return;
      setState(() {
        _rules=data[0]; _incidents=data[1];
        _loading=false; _error=null;
      });
    } catch (_) {
      if(!mounted || generation != _generation)return;
      setState(() {
        _loading=false;
        _error='Alert service unavailable or not activated.';
      });
    }
  }

  Future<void> _write(Future<void> Function() task) async {
    if(_busy)return;
    setState(() { _busy=true; _error=null; });
    try {
      await task();
      await _load();
    } catch (_) {
      if (mounted) {
        setState(() => _error =
          'Alert action failed or permission was denied.');
      }
    } finally {
      if(mounted)setState(() => _busy=false);
    }
  }

  Future<void> _create() async {
    final hostId=_hostId ?? (widget.hosts.isEmpty ? null : widget.hosts.first.id);
    final threshold=double.tryParse(_threshold.text.trim());
    if(hostId == null || threshold == null ||
       threshold < 1 || threshold > 100) {
      setState(() => _error='Select a host and a threshold of 1–100%.');
      return;
    }
    await _write(() async {
      final workspace=await alertWorkspace(widget.api);
      await alertRequest(widget.api,'POST',['rules'],body:{
        'workspace_id':workspace,
        'host_id':hostId,
        'metric':_metric,
        'threshold_pct':threshold,
        'consecutive_required':2,
      });
    });
  }

  Future<void> _edit(Map<String,dynamic> rule) async {
    final input=TextEditingController(
      text:(rule['threshold_pct'] as num).toString());
    final next=await showDialog<double>(context:context,
      builder:(ctx) => AlertDialog(
        title:const Text('Edit threshold'),
        content:TextField(controller:input,
          decoration:const InputDecoration(labelText:'Threshold %'),
          keyboardType:const TextInputType.numberWithOptions(decimal:true)),
        actions:[
          TextButton(onPressed:()=>Navigator.pop(ctx),
            child:const Text('Cancel')),
          FilledButton(onPressed:(){
            final value=double.tryParse(input.text.trim());
            if(value == null || value < 1 || value > 100)return;
            Navigator.pop(ctx,value);
          },child:const Text('Save')),
        ],
      ));
    input.dispose();
    if(next == null)return;
    await _write(() async {
      await alertRequest(widget.api,'PATCH',
        ['rules',rule['id'] as String],body:{'threshold_pct':next});
    });
  }

  Future<void> _archive(Map<String,dynamic> rule) async {
    final approved=await showDialog<bool>(context:context,
      builder:(ctx) => AlertDialog(
        title:const Text('Archive alert rule?'),
        content:const Text('This stops the rule. Incident history is retained.'),
        actions:[
          TextButton(onPressed:()=>Navigator.pop(ctx,false),
            child:const Text('Cancel')),
          FilledButton(onPressed:()=>Navigator.pop(ctx,true),
            child:const Text('Archive')),
        ],
      ));
    if(approved != true)return;
    await _write(() async {
      await alertRequest(widget.api,'DELETE',['rules',rule['id'] as String]);
    });
  }

  Future<void> _ack(Map<String,dynamic> incident) async {
    await _write(() async {
      await alertRequest(widget.api,'POST',
        ['incidents',incident['id'] as String,'acknowledge']);
    });
  }

  String _hostName(String id) {
    for(final host in widget.hosts) {
      if(host.id == id)return host.name;
    }
    return 'Removed host';
  }

  @override
  Widget build(BuildContext context) {
    final target=widget.hosts.any((h)=>h.id==_hostId)
      ? _hostId : (widget.hosts.isEmpty ? null : widget.hosts.first.id);
    final active=_incidents.where((x)=>
      x['status']=='OPEN' || x['status']=='ACKNOWLEDGED').length;
    return Container(
      padding:const EdgeInsets.all(20),
      decoration:BoxDecoration(
        color:const Color(0xFF111D30),
        border:Border.all(color:const Color(0xFF27374E)),
        borderRadius:BorderRadius.circular(17)),
      child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
        Row(children:[
          const Expanded(child:Text('ALERT RULES & INCIDENTS',
            style:TextStyle(fontSize:16,fontWeight:FontWeight.w800))),
          Text(active.toString()+' active',
            style:const TextStyle(color:Color(0xFFF6BE69),fontSize:11)),
          IconButton(tooltip:'Refresh alerts',
            onPressed:_busy ? null:_load,
            icon:const Icon(Icons.refresh_rounded)),
        ]),
        const Text('Triggered by real accepted agent measurements',
          style:TextStyle(color:Color(0xFFA1AFCA),fontSize:11)),
        const SizedBox(height:13),
        if(_loading)const LinearProgressIndicator(minHeight:2),
        if(_error != null)Padding(
          padding:const EdgeInsets.symmetric(vertical:9),
          child:Text(_error!,style:const TextStyle(
            color:Color(0xFFF6BE69),fontSize:11))),
        Wrap(spacing:12,runSpacing:9,
          crossAxisAlignment:WrapCrossAlignment.center,children:[
          SizedBox(width:190,child:DropdownButtonFormField<String>(
            key:ValueKey('rule-host-'+(target ?? 'none')),
            initialValue:target,
            decoration:const InputDecoration(labelText:'Host'),
            items:widget.hosts.map((h)=>DropdownMenuItem(
              value:h.id,child:Text(h.name,
                overflow:TextOverflow.ellipsis))).toList(),
            onChanged:_busy?null:(v)=>setState(()=>_hostId=v),
          )),
          SizedBox(width:140,child:DropdownButtonFormField<String>(
            initialValue:_metric,
            decoration:const InputDecoration(labelText:'Metric'),
            items:const [
              DropdownMenuItem(value:'cpu_pct',child:Text('CPU')),
              DropdownMenuItem(value:'ram_pct',child:Text('RAM')),
              DropdownMenuItem(value:'disk_pct',child:Text('Disk')),
            ],
            onChanged:_busy?null:(v){
              if(v!=null)setState(()=>_metric=v);
            },
          )),
          SizedBox(width:125,child:TextField(
            controller:_threshold,
            keyboardType:const TextInputType.numberWithOptions(decimal:true),
            decoration:const InputDecoration(labelText:'Threshold %'),
          )),
          FilledButton.icon(
            onPressed:_busy?null:_create,
            icon:const Icon(Icons.add),
            label:const Text('Create rule')),
        ]),
        const SizedBox(height:12),
        if(!_loading && _rules.isEmpty)
          const Text('No alert rules configured',
            style:TextStyle(color:Color(0xFFA1AFCA),fontSize:11)),
        for(final rule in _rules)
          ListTile(
            contentPadding:EdgeInsets.zero,
            title:Text(_hostName(rule['host_id'] as String)+' · '+
              (rule['metric'] as String).replaceAll('_pct','').toUpperCase()+
              ' ≥ '+(rule['threshold_pct'] as num).toStringAsFixed(1)+'%',
              style:const TextStyle(fontSize:12)),
            subtitle:Text((rule['enabled'] as bool)?
              'Enabled · 2 consecutive samples':'Disabled',
              style:const TextStyle(fontSize:10,color:Color(0xFFA1AFCA))),
            trailing:PopupMenuButton<String>(
              tooltip:'Rule actions',
              onSelected:(a){
                if(a=='edit')_edit(rule);
                if(a=='archive')_archive(rule);
              },
              itemBuilder:(_)=>const [
                PopupMenuItem(value:'edit',child:Text('Edit')),
                PopupMenuItem(value:'archive',child:Text('Archive')),
              ]),
          ),
        const Divider(color:Color(0xFF27374E)),
        const Text('INCIDENTS',style:TextStyle(
          color:Color(0xFFA1AFCA),fontSize:11,fontWeight:FontWeight.w800)),
        if(!_loading && _incidents.isEmpty)
          const Padding(padding:EdgeInsets.symmetric(vertical:12),
            child:Text('No incidents recorded.',
              style:TextStyle(color:Color(0xFFA1AFCA),fontSize:11))),
        for(final incident in _incidents.take(15))
          ListTile(
            contentPadding:EdgeInsets.zero,
            title:Text(_hostName(incident['host_id'] as String)+' · '+
              (incident['metric'] as String).replaceAll('_pct','').toUpperCase(),
              style:const TextStyle(fontSize:12)),
            subtitle:Text((incident['status'] as String)+' · '+
              (incident['last_value'] as num).toStringAsFixed(1)+'%',
              style:const TextStyle(color:Color(0xFFA1AFCA),fontSize:11)),
            trailing:incident['status']=='OPEN'?
              OutlinedButton(
                onPressed:_busy?null:()=>_ack(incident),
                child:const Text('Acknowledge')):null),
      ]),
    );
  }
}
