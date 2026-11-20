import 'dart:async';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'data/fleet_api.dart';
import 'state/fleet_controller.dart';
import 'ui/fleet_screen.dart';
import 'ui/sign_in_screen.dart';
import 'ui/sign_up_screen.dart';

const apiBaseUrl = String.fromEnvironment(
  'FLEETLUMA_API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);
const cloudMode = bool.fromEnvironment('FLEETLUMA_CLOUD_MODE');
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
      return _showSignUp
          ? SignUpScreen(
              registrationEnabled: registrationEnabled,
              onBackToSignIn: () => setState(() => _showSignUp = false),
            )
          : SignInScreen(
              registrationEnabled: registrationEnabled,
              onCreateAccount: () => setState(() => _showSignUp = true),
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
  }
}
