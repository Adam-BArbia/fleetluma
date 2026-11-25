import 'package:fleetluma/main.dart' show FleetLumaStartupFailure;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('cloud startup failure is visible instead of a blank screen',
      (tester) async {
    await tester.pumpWidget(const FleetLumaStartupFailure());

    expect(find.text('FleetLuma could not start'), findsOneWidget);
    expect(find.textContaining('Check your connection'), findsOneWidget);
    expect(find.byIcon(Icons.cloud_off_outlined), findsOneWidget);
    expect(find.byType(Scaffold), findsOneWidget);
  });
}
