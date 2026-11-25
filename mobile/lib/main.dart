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
    try {
      if (!apiBaseUrl.startsWith('https://') ||
          !supabaseUrl.startsWith('https://') ||
          supabasePublishableKey.isEmpty) {
        throw StateError('Invalid cloud startup configuration');
      }
      await Supabase.initialize(
        url: supabaseUrl,
        publishableKey: supabasePublishableKey,
        debug: false,
      );
    } catch (error) {
      // Never render a blank page if cloud initialization fails before runApp.
      // Do not print credentials, request bodies or provider error messages.
      debugPrint('FleetLuma cloud startup failed: ${error.runtimeType}');
      runApp(const FleetLumaStartupFailure());
      return;
    }
  }
  runApp(const FleetLumaApp());
}

/// Non-sensitive, actionable error UI for failures before Supabase is ready.
/// This widget has no backend requests and cannot bypass operator approval.
class FleetLumaStartupFailure extends StatelessWidget {
  const FleetLumaStartupFailure({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'FleetLuma - unavailable',
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark(useMaterial3: true),
        home: Scaffold(
          backgroundColor: const Color(0xFF080E1A),
          body: SafeArea(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: const [
                      Icon(Icons.cloud_off_outlined,
                          size: 48, color: Color(0xFFFF8D95)),
                      SizedBox(height: 22),
                      Text('FleetLuma could not start',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: 25, fontWeight: FontWeight.w700)),
                      SizedBox(height: 12),
                      Text(
                        'The monitoring dashboard is temporarily unavailable. '
                        'Check your connection and reload the page. '
                        'If the problem continues, contact the administrator.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            height: 1.5, color: Color(0xFFA1AFCA)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );
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
        scaffoldBackgroundColor: const Color(0xFF080E1A),
        colorScheme: ColorScheme.fromSeed(
          seedColor: cyan,
          brightness: Brightness.dark,
          surface: const Color(0xFF111D30),
        ).copyWith(
          primary: cyan,
          onPrimary: navy,
          secondary: const Color(0xFF86A7FF),
          onSurface: const Color(0xFFF3F7FF),
          outline: const Color(0xFF33465F),
          error: const Color(0xFFFF8D95),
        ),
        textTheme: const TextTheme(
          headlineMedium: TextStyle(
            fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -0.8),
          titleLarge: TextStyle(
            fontSize: 21, fontWeight: FontWeight.w800, letterSpacing: -0.4),
          titleMedium: TextStyle(fontWeight: FontWeight.w700),
          bodyMedium: TextStyle(height: 1.45),
        ),
        cardTheme: CardThemeData(
          color: const Color(0xFF111D30),
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: const BorderSide(color: Color(0xFF27374E)),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF0D1728),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 16, vertical: 17),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFF34475C))),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFF34475C))),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: cyan, width: 1.5)),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size(0, 46),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12)),
            textStyle: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(0, 46),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12)),
            side: const BorderSide(color: Color(0xFF34475C)),
          ),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF080E1A),
          surfaceTintColor: Colors.transparent,
          foregroundColor: Colors.white,
        ),
        dividerTheme: const DividerThemeData(
          color: Color(0xFF24354B), thickness: 1),
      ),
      routes: cloudMode && pairingUiEnabled
          ? {'/devices/pair': (_) => const _CloudAuthGate(openDevicesOnLogin: true)}
          : const {},
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
  final bool openDevicesOnLogin;
  const _CloudAuthGate({this.openDevicesOnLogin = false});

  @override
  State<_CloudAuthGate> createState() => _CloudAuthGateState();
}

class _CloudAuthGateState extends State<_CloudAuthGate> {
  StreamSubscription<AuthState>? _authSubscription;
  bool _showSignUp = false;
  String? _authorizedToken;
  Future<void>? _authorization;
  String? _authorizedWorkspaceId;
  bool _didOpenPairingDeepLink = false;

  void _openDeviceManagement(BuildContext context, GoTrueClient auth) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => DeviceManagementScreen(
        api: HttpFleetDeviceApi(
          baseUrl: apiBaseUrl,
          tokenProvider: () async => auth.currentSession?.accessToken,
        ),
      ),
    ));
  }

  Future<void> _checkOperatorAccess(String token) async {
    if (pairingUiEnabled) {
      final manager = HttpFleetDeviceApi(
        baseUrl: apiBaseUrl,
        tokenProvider: () async => token,
      );
      final permitted = await manager.workspaces();
      if (permitted.isEmpty) {
        throw const FleetAccessDeniedException();
      }
      final workspace = permitted.first.id;
      await HttpFleetApi(
        baseUrl: apiBaseUrl,
        tokenProvider: () async => token,
        workspaceIdProvider: () async => workspace,
      ).fetchHosts();
      _authorizedWorkspaceId = workspace;
    } else {
      await HttpFleetApi(baseUrl: apiBaseUrl, tokenProvider: () async => token)
          .fetchHosts();
      _authorizedWorkspaceId = null;
    }
  }

  void _retryAccess() {
    setState(() {
      _authorizedToken = null;
      _authorization = null;
      _authorizedWorkspaceId = null;
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
      _authorizedWorkspaceId = null;
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
        if (widget.openDevicesOnLogin && pairingUiEnabled &&
            !_didOpenPairingDeepLink) {
          _didOpenPairingDeepLink = true;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) _openDeviceManagement(context, auth);
          });
        }
        return FleetScreen(
          key: ValueKey(session.user.id),
          controller: FleetController(
            api: HttpFleetApi(
              baseUrl: apiBaseUrl,
              tokenProvider: () async => auth.currentSession?.accessToken,
              workspaceIdProvider: pairingUiEnabled
                  ? () async => _authorizedWorkspaceId
                  : null,
            ),
          ),
          apiUrl: apiBaseUrl,
          onSignOut: () async => auth.signOut(),
          onManageDevices: pairingUiEnabled
              ? () => _openDeviceManagement(context, auth)
              : null,
        );
      },
    );
  }
}
