import 'package:fleetluma/ui/sign_in_screen.dart';
import 'package:fleetluma/ui/sign_up_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Sign in has a link to request a restricted operator account',
      (tester) async {
    var opened = false;
    await tester.pumpWidget(MaterialApp(
      home: SignInScreen(
        registrationEnabled: false,
        onCreateAccount: () => opened = true,
      ),
    ));
    expect(find.text('Operator sign in'), findsOneWidget);
    await tester.tap(find.text('Request an account'));
    expect(opened, isTrue);
  });

  testWidgets('Disabled registration never shows credential fields or submit',
      (tester) async {
    var returned = false;
    await tester.pumpWidget(MaterialApp(
      home: SignUpScreen(
        registrationEnabled: false,
        onBackToSignIn: () => returned = true,
      ),
    ));
    expect(find.text('Create operator account'), findsOneWidget);
    expect(find.textContaining('invitation-only'), findsOneWidget);
    expect(find.byType(TextFormField), findsNothing);
    expect(find.text('Create account'), findsNothing);
    await tester.tap(find.text('Back to sign in'));
    expect(returned, isTrue);
  });

  testWidgets('Enabled registration requires all three input fields',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: SignUpScreen(
        registrationEnabled: true,
        onBackToSignIn: () {},
      ),
    ));
    expect(find.byType(TextFormField), findsNWidgets(3));
    await tester.ensureVisible(find.text('Create account'));
    await tester.tap(find.text('Create account'));
    await tester.pump();
    expect(find.text('Enter a valid email address'), findsOneWidget);
    expect(find.text('Use at least 12 characters'), findsOneWidget);
  });
}
