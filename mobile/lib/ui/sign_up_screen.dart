import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// User registration only creates a Supabase identity. Fleet API access still
/// requires the UUID to appear in the backend's explicit operator allowlist.
/// Signup must also be enabled in Supabase Auth; client flag alone is not security.
class SignUpScreen extends StatefulWidget {
  final bool registrationEnabled;
  final VoidCallback onBackToSignIn;

  const SignUpScreen({
    super.key,
    required this.registrationEnabled,
    required this.onBackToSignIn,
  });

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirmation = TextEditingController();
  bool _submitting = false;
  bool _obscure = true;
  String? _error;
  bool _submitted = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  Future<void> _signUp() async {
    if (_submitting || !widget.registrationEnabled || !_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final result = await Supabase.instance.client.auth.signUp(
        email: _email.text.trim(),
        password: _password.text,
      );
      // A user is NOT an approved operator merely because Auth signed them up.
      // Supabase may return a session when email confirmation is disabled.
      // Immediately end such a session to avoid accidental dashboard mounting.
      if (result.session != null) {
        await Supabase.instance.client.auth.signOut();
      }
      if (mounted) setState(() => _submitted = true);
    } on AuthException {
      if (mounted) {
        setState(() => _error = 'Registration could not be completed. Check your details or contact the administrator.');
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Cannot reach the authentication service.');
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
              constraints: const BoxConstraints(maxWidth: 460),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.shield_outlined, size: 42, color: Color(0xFF55E5D3)),
                      const SizedBox(height: 14),
                      const Text('FleetLuma', textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 27, fontWeight: FontWeight.w800)),
                      const SizedBox(height: 8),
                      Text(_submitted ? 'Check your email' : 'Create operator account',
                          textAlign: TextAlign.center, style: const TextStyle(fontSize: 18)),
                      const SizedBox(height: 18),
                      if (!widget.registrationEnabled)
                        const Text(
                          'Account creation is invitation-only for this fleet. '
                          'Ask the project administrator to enable registration or provision your account. '
                          'Registration never grants monitoring access automatically.',
                          textAlign: TextAlign.center,
                        )
                      else if (_submitted)
                        const Text(
                          'If registration was accepted, check your inbox to confirm your email. '
                          'An administrator must also approve your operator account before fleet data is accessible.',
                          textAlign: TextAlign.center,
                        )
                      else
                        Form(
                          key: _formKey,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              TextFormField(
                                controller: _email,
                                keyboardType: TextInputType.emailAddress,
                                autofillHints: const [AutofillHints.email],
                                decoration: const InputDecoration(labelText: 'Email',
                                    prefixIcon: Icon(Icons.mail_outline)),
                                validator: (value) {
                                  final v = value?.trim() ?? '';
                                  if (!v.contains('@') || v.startsWith('@') || v.endsWith('@')) {
                                    return 'Enter a valid email address';
                                  }
                                  return null;
                                },
                              ),
                              const SizedBox(height: 14),
                              TextFormField(
                                controller: _password,
                                obscureText: _obscure,
                                autofillHints: const [AutofillHints.newPassword],
                                decoration: InputDecoration(
                                  labelText: 'Password (12+ characters)',
                                  prefixIcon: const Icon(Icons.lock_outline),
                                  suffixIcon: IconButton(
                                    tooltip: _obscure ? 'Show password' : 'Hide password',
                                    onPressed: () => setState(() => _obscure = !_obscure),
                                    icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                                  ),
                                ),
                                validator: (value) =>
                                    (value?.length ?? 0) < 12 ? 'Use at least 12 characters' : null,
                              ),
                              const SizedBox(height: 14),
                              TextFormField(
                                controller: _confirmation,
                                obscureText: _obscure,
                                autofillHints: const [AutofillHints.newPassword],
                                decoration: const InputDecoration(
                                  labelText: 'Confirm password', prefixIcon: Icon(Icons.verified_user_outlined)),
                                validator: (value) =>
                                    value != _password.text ? 'Passwords do not match' : null,
                              ),
                              if (_error != null) ...[
                                const SizedBox(height: 12),
                                Text(_error!, style: const TextStyle(color: Colors.orangeAccent)),
                              ],
                              const SizedBox(height: 22),
                              FilledButton(
                                onPressed: _submitting ? null : _signUp,
                                child: Text(_submitting ? 'Creating account…' : 'Create account'),
                              ),
                              const SizedBox(height: 12),
                              const Text(
                                'Verify your email before signing in. Account approval is separate '
                                'and handled by the fleet administrator.',
                                textAlign: TextAlign.center, style: TextStyle(fontSize: 12),
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 18),
                      TextButton.icon(
                        onPressed: widget.onBackToSignIn,
                        icon: const Icon(Icons.arrow_back),
                        label: const Text('Back to sign in'),
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
