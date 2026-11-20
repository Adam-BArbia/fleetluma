import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Operator login only. Account provisioning is restricted to project admins.
class SignInScreen extends StatefulWidget {
  final bool registrationEnabled;
  final VoidCallback onCreateAccount;

  const SignInScreen({super.key, required this.registrationEnabled, required this.onCreateAccount});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    if (_submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await Supabase.instance.client.auth.signInWithPassword(
        email: _email.text.trim(),
        password: _password.text,
      );
      // AuthState listener in main.dart navigates to the dashboard.
    } on AuthException {
      if (mounted) {
        setState(() => _error = 'Sign-in failed. Check your credentials.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to reach the authentication service.');
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Icon(Icons.radar_rounded,
                          size: 42, color: Color(0xFF55E5D3)),
                      const SizedBox(height: 14),
                      const Text('FleetLuma',
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 27,
                              fontWeight: FontWeight.w800)),
                      const SizedBox(height: 6),
                      const Text('Operator sign in',
                          textAlign: TextAlign.center),
                      const SizedBox(height: 24),
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        decoration: const InputDecoration(
                            labelText: 'Email',
                            prefixIcon: Icon(Icons.mail_outline)),
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        controller: _password,
                        obscureText: true,
                        autofillHints: const [AutofillHints.password],
                        onSubmitted: (_) => _signIn(),
                        decoration: const InputDecoration(
                            labelText: 'Password',
                            prefixIcon: Icon(Icons.lock_outline)),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(_error!,
                            style: const TextStyle(color: Colors.orangeAccent)),
                      ],
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: _submitting ? null : _signIn,
                        child: Text(_submitting ? 'Signing in…' : 'Sign in'),
                      ),
                      const SizedBox(height: 12),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        onPressed: widget.onCreateAccount,
                        icon: const Icon(Icons.person_add_alt_outlined),
                        label: Text(widget.registrationEnabled
                            ? 'Create an account'
                            : 'Request an account'),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Only approved operators can view FleetLuma monitoring data. '
                        'Agent credentials are separate from operator accounts.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 12, color: Colors.white60),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
