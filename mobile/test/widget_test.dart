import 'package:fleetluma/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Flutter mobile has a configurable coordinator API base URL', () {
    expect(apiBaseUrl, startsWith('http'));
  });
}
