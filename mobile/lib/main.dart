import 'dart:async';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'data/fleet_api.dart';
import 'data/device_api.dart';
import 'state/fleet_controller.dart';
import 'ui/fleet_screen.dart';
import 'ui/device_management_screen.dart';
import 'ui/sign_in_screen.dart';
import 'ui/sign_up_screen.dart';

const apiBaseUrl = String.fromEnvironment(
  'FLEETLUMA_API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);
const cloudMode = bool.fromEnvironment('FLEETLUMA_CLOUD_MODE');
// Hidden until server migration + workspace-scoped API are actually deployed.
const pairingUiEnabled = bool.fromEnvironment('FLEETLUMA_PAIRING_UI_ENABLED');
// UI feature gate, NOT an authorization boundary. Set Supabase Auth policy separately.
const registrationEnabled = bool.fromEnvironment('FLEETLUMA_ALLOW_SIGN_UP');
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
  bool _showSignUp = false;
  String? _authorizedToken;
  Future<void>? _authorization;

  Future<void> _checkOperatorAccess(String token) async {
    await HttpFleetApi(baseUrl: apiBaseUrl, tokenProvider: () async => token)
        .fetchHosts();
  }

  void _retryAccess() {
    setState(() {
      _authorizedToken = null;
      _authorization = null;
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
    // Keep the registration form mounted even if the Auth provider briefly
    // issues a new session before email confirmation or explicit sign-out.
    if (_showSignUp) {
      return SignUpScreen(
        registrationEnabled: registrationEnabled,
        onBackToSignIn: () => setState(() => _showSignUp = false),
      );
    }
    if (session == null) {
      return SignInScreen(
        registrationEnabled: registrationEnabled,
        onCreateAccount: () => setState(() => _showSignUp = true),
      );
    }
    // A Supabase session does not imply FleetLuma operator approval.
    // Do not mount FleetScreen (or begin polling) until the API approves it.
    final token = session.accessToken;
    if (_authorization == null || _authorizedToken != token) {
      _authorizedToken = token;
      _authorization = _checkOperatorAccess(token);
    }
    return FutureBuilder<void>(
      future: _authorization,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snapshot.hasError) {
          final denied = snapshot.error is FleetAccessDeniedException;
          final expired = snapshot.error is FleetSessionExpiredException;
          return Scaffold(
            appBar: AppBar(title: const Text('FleetLuma account access')),
            body: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.lock_person_outlined, size: 52),
                      const SizedBox(height: 16),
                      Text(
                        denied
                            ? 'Waiting for operator approval'
                            : expired
                                ? 'Your session needs to be renewed'
                                : 'Unable to verify access',
                        style: Theme.of(context).textTheme.titleLarge,
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        denied
                            ? 'Your account exists but has not been approved to view monitoring data.'
                            : expired
                                ? 'Sign in again to refresh your session.'
                                : 'The monitoring service could not confirm your access. Try again later.',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: _retryAccess,
                        child: const Text('Retry access check'),
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton(
                        onPressed: () async => auth.signOut(),
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
          onManageDevices: pairingUiEnabled ? () {
            Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => DeviceManagementScreen(
                api: HttpFleetDeviceApi(
                  baseUrl: apiBaseUrl,
                  tokenProvider: () async => auth.currentSession?.accessToken,
                ),
              ),
            ));
          } : null,
        );
      },
    );
  }
}
