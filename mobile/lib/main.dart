import 'package:flutter/material.dart';

import 'data/fleet_api.dart';
import 'state/fleet_controller.dart';
import 'ui/fleet_screen.dart';

const apiBaseUrl = String.fromEnvironment(
  'FLEETLUMA_API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
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
      home: FleetScreen(
        controller: controller ??
            FleetController(api: HttpFleetApi(baseUrl: apiBaseUrl)),
        apiUrl: apiBaseUrl,
      ),
    );
  }
}
