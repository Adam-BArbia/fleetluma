import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Cloud operator self-registration is opt-in and NEVER grants fleet access.
/// A project administrator must still approve the user's UUID in
/// FLEETLUMA_OPERATOR_IDS on the FastAPI server.
const allowSelfSignup = bool.fromEnvironment(
  'FLEETLUMA_ALLOW_SELF_SIGNUP',
  defaultValue: false,
);

class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirmPassword = TextEditingController();
  bool _submitting = false;
  bool _submitted = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _confirmPassword.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    if (!allowSelfSignup || _submitting || !_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await Supabase.instance.client.auth.signUp(
        email: _email.text.trim(),
        password: _password.text,
      );
      // Never assume signUp created an authorized operator. Even if Supabase
      // issues a session, FastAPI only permits explicitly allowlisted UUIDs.
      if (mounted) setState(() => _submitted = true);
    } on AuthException {
      if (mounted) {
        setState(() => _error =
            'Registration could not be completed. Check your details or contact your administrator.');
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
      appBar: AppBar(title: const Text('Create an account')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.person_add_alt_1,
                          color: Color(0xFF55E5D3), size: 42),
                      const SizedBox(height: 16),
                      const Text('FleetLuma operator registration',
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 14),
                      if (!allowSelfSignup)
                        const Text(
                          'Accounts are invitation-only. Ask the FleetLuma administrator '
                          'to provision an operator account. Registration is disabled.',
                          textAlign: TextAlign.center,
                        )
                      else if (_submitted)
                        const Text(
                          'If registration was accepted, check your inbox to confirm '
                          'your email. A FleetLuma administrator must approve your '
                          'operator account before you can view any monitoring data.',
                          textAlign: TextAlign.center,
                        )
                      else ...[
                        const Text(
                          'Registration is open for this deployment, but fleet access '
                          'requires separate administrator approval.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 20),
                        Form(
                          key: _formKey,
                          child: Column(
                            children: [
                              TextFormField(
                                controller: _email,
                                keyboardType: TextInputType.emailAddress,
                                autofillHints: const [AutofillHints.email],
                                decoration: const InputDecoration(
                                  labelText: 'Email',
                                  prefixIcon: Icon(Icons.mail_outline),
                                ),
                                validator: (value) {
                                  final email = value?.trim() ?? '';
                                  if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                                      .hasMatch(email)) {
                                    return 'Enter a valid email address';
                                  }
                                  return null;
                                },
                              ),
                              const SizedBox(height: 16),
                              TextFormField(
                                controller: _password,
                                obscureText: true,
                                autofillHints: const [AutofillHints.newPassword],
                                decoration: const InputDecoration(
                                  labelText: 'Password (12+ characters)',
                                  prefixIcon: Icon(Icons.lock_outline),
                                ),
                                validator: (value) => (value?.length ?? 0) < 12
                                    ? 'Use at least 12 characters'
                                    : null,
                              ),
                              const SizedBox(height: 16),
                              TextFormField(
                                controller: _confirmPassword,
                                obscureText: true,
                                decoration: const InputDecoration(
                                  labelText: 'Confirm password',
                                  prefixIcon: Icon(Icons.lock_reset_outlined),
                                ),
                                validator: (value) => value != _password.text
                                    ? 'Passwords do not match'
                                    : null,
                              ),
                            ],
                          ),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 14),
                          Text(_error!,
                              style: const TextStyle(color: Colors.orangeAccent)),
                        ],
                        const SizedBox(height: 22),
                        FilledButton(
                          onPressed: _submitting ? null : _register,
                          child: Text(_submitting ? 'Creating account…' : 'Sign up'),
                        ),
                      ],
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('Back to sign in'),
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
