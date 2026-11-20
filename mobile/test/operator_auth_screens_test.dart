import 'package:fleetluma/ui/sign_in_screen.dart';
import 'package:fleetluma/ui/sign_up_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Sign-in screen has accessible account creation navigation',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: SignInScreen()),
    );
    expect(find.text('Operator sign in'), findsOneWidget);
    final signupLink = find.text('Create an account / Request access');
    expect(signupLink, findsOneWidget);
    await tester.tap(signupLink);
    await tester.pumpAndSettle();
    expect(find.text('FleetLuma operator registration'), findsOneWidget);
  });

  testWidgets('Public account registration is disabled by default',
      (tester) async {
    expect(allowSelfSignup, isFalse);
    await tester.pumpWidget(
      const MaterialApp(home: SignUpScreen()),
    );
    expect(find.textContaining('invitation-only'), findsOneWidget);
    expect(find.text('Sign up'), findsNothing);
    expect(find.text('Back to sign in'), findsOneWidget);
  });
}
