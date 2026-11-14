# FleetLuma Flutter Android client — FL-9

Mobile-first Fleet overview for the **real FastAPI** `GET /api/v1/hosts` endpoint.
There is no hard-coded or sample fleet in the production application.

## Requirements and installation

- Flutter stable, Android SDK, device or Android emulator.
- Python coordinator started with a provisioned host (see `backend/README.md`).
- A reporting agent (see `agent/README.md`).
- **One-time Android scaffold:** after cloning, from `mobile/` run
  `flutter create --platforms=android --project-name fleetluma .`.
  Android Gradle boilerplate is intentionally generated from Flutter, not committed by FL-9.
  The version-controlled `android/app/src/main/AndroidManifest.xml` adds the INTERNET
  permission and permits **cleartext HTTP only for a controlled laboratory LAN**.
  Verify `flutter create` preserves it before running; replace it if the
  template overwrites the file.
- Run `flutter pub get`, `flutter analyze`, and `flutter test`.

## Run on Android emulator

```bash
cd mobile
flutter create --platforms=android --project-name fleetluma .
flutter pub get
flutter run --dart-define=FLEETLUMA_API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the standard Android emulator's route to the computer's
localhost. The FastAPI coordinator must be running on that same computer.
If using a **physical phone**, replace the URL with the server's reachable
LAN IPv4 address and bind FastAPI to `0.0.0.0` on that trusted network;
open only the required firewall port.

A public or untrusted Wi-Fi is unsafe for the demo HTTP bearer-token transport.
Production requires HTTPS, private agent credentials and authenticated viewer routes.
The app never sends agent tokens.

## Scope and behavior

- Responsive Fleet overview with host counts and CPU/RAM/disk percentage/usage.
- **CONNECTED**, **PENDING**, and **STALE** are backend states: stale does not mean the server is powered off.
- Stale measurements are clearly labeled as last known, **not live**.
- Loading, empty, and error states with manual refresh/pull-to-refresh.
- Polls the backend every five seconds while the app is active;
  polls are paused while backgrounded, and overlapping calls are prevented.
- On network failure after a successful fetch, old data remains visible
  with a connection warning rather than being represented as fresh.
- Works with the exact `HostList` schema in `docs/api/openapi.json`.
- Future detail/history/process/service screens are tracked by FL-11, FL-12 and FL-10.

## Testing

`flutter test` covers payload parsing, state semantics, empty fleet,
connected/stale readings and API failure. GitHub Actions runs Flutter
analysis, widget tests, Android scaffold generation and debug APK build.

**Honest limitations:** FL-9's GitHub Actions build and widget tests
verify code quality, not an actual physical-phone/LAN demonstration.
Full real-device integration belongs to FL-13.
