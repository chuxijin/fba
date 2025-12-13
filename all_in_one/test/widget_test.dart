import 'package:flutter_test/flutter_test.dart';

import 'package:appflowy_login/main.dart';

void main() {
  testWidgets('AppFlowy Login Screen smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const AppFlowyLoginApp());

    // Verify that our login screen is displayed.
    expect(find.text('Welcome to AppFlowy'), findsOneWidget);
    expect(find.text('Sign in to your account'), findsOneWidget);
  });
}
