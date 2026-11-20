import 'dart:async';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'data/fleet_api.dart';
import 'state/fleet_controller.dart';
import 'ui/fleet_screen.dart';
import 'ui/sign_in_screen.dart';

const apiBaseUrl = String.fromEnvironment(
  'FLEETLUMA_API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);
const cloudMode = bool.fromEnvironment('FLEETLUMA_CLOUD_MODE');
const supabaseUrl = String.fromEnvironment('FLEETLUMA_SUPABASE_URL');
const supabasePublishableKey = String.fromEnvironment(
  'FLEETLUMA_SUPABASE_PUBLISHABLE_KEY',
);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (cloudMode) {
    if (!apiBaseUrl.startsWith('https://') ||
        !supabaseUrl.startsWith('https://') ||
        supabasePublishableKey.isEmpty) {
      throw StateError('Cloud mode requires HTTPS API, Supabase URL and publishable key');
    }
    await Supabase.initialize(
      url: supabaseUrl,
      publishableKey: supabasePublishableKey,
      debug: false,
    );
  }
  runApp(const FleetLumaApp());
}

class FleetLumaApp extends StatelessWidget {
  final FleetController? controller;
  const FleetLumaApp({super.key, this.controller});

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0B1222);
    const cyan = Color(0xFF55E5D3);
    return MaterialApp(
      title: 'FleetLuma',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: navy,
        colorScheme: ColorScheme.fromSeed(
          seedColor: cyan,
          brightness: Brightness.dark,
          surface: const Color(0xFF151F34),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: navy,
          foregroundColor: Colors.white,
        ),
      ),
      home: cloudMode
          ? const _CloudAuthGate()
          : FleetScreen(
              controller: controller ??
                  FleetController(api: HttpFleetApi(baseUrl: apiBaseUrl)),
              apiUrl: apiBaseUrl,
            ),
    );
  }
}

/// The FleetScreen is not mounted and never polls until a session exists.
class _CloudAuthGate extends StatefulWidget {
  const _CloudAuthGate();

  @override
  State<_CloudAuthGate> createState() => _CloudAuthGateState();
}

class _CloudAuthGateState extends State<_CloudAuthGate> {
  StreamSubscription<AuthState>? _authSubscription;
  String? _verifiedForToken;
  Future<void>? _permissionCheck;

  Future<void> _verifyOperator(String token) async {
    await HttpFleetApi(
      baseUrl: apiBaseUrl,
      tokenProvider: () async => token,
    ).fetchHosts();
  }

  void _retryAuthorization() {
    setState(() {
      _permissionCheck = null;
      _verifiedForToken = null;
    });
  }

  @override
  void initState() {
    super.initState();
    _authSubscription = Supabase.instance.client.auth.onAuthStateChange.listen(
      (_) {
        if (mounted) setState(() {});
      },
    );
  }

  @override
  void dispose() {
    _authSubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = Supabase.instance.client.auth;
    final session = auth.currentSession;
    if (session == null) {
      return const SignInScreen();
    }
    // Authentication alone is insufficient. A signed-in user can exist in
    // Supabase without being on the backend operator allowlist.
    final accessToken = session.accessToken;
    if (_permissionCheck == null || _verifiedForToken != accessToken) {
      _verifiedForToken = accessToken;
      _permissionCheck = _verifyOperator(accessToken);
    }
    return FutureBuilder<void>(
      future: _permissionCheck,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snapshot.hasError) {
          final rejected = snapshot.error is FleetAccessDeniedException;
          final expired = snapshot.error is FleetSessionExpiredException;
          return Scaffold(
            appBar: AppBar(title: const Text('FleetLuma account access')),
            body: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(rejected ? Icons.lock_person_outlined : Icons.cloud_off_outlined,
                          size: 48),
                      const SizedBox(height: 16),
                      Text(
                        rejected
                            ? 'Waiting for operator approval'
                            : expired
                                ? 'Your session needs to be renewed'
                                : 'Unable to verify access',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        rejected
                            ? 'Your Supabase account is signed in but your FleetLuma '
                              'operator ID has not been approved by an administrator.'
                            : 'The protected FleetLuma API could not confirm your '
                              'permissions. No monitoring data was loaded.',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 24),
                      OutlinedButton(
                        onPressed: _retryAuthorization,
                        child: const Text('Retry verification'),
                      ),
                      TextButton(
                        onPressed: () async {
                          await Supabase.instance.client.auth.signOut();
                        },
                        child: const Text('Sign out'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        }
        return FleetScreen(
          key: ValueKey(session.user.id),
      controller: FleetController(
        api: HttpFleetApi(
          baseUrl: apiBaseUrl,
          tokenProvider: () async => auth.currentSession?.accessToken,
        ),
      ),
      apiUrl: apiBaseUrl,
          onSignOut: () async => auth.signOut(),
        );
      },
    );
  }
}
