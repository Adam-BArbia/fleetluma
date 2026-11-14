# FL-17 — Flutter Web build and HTTP client migration

**Status:** Browser build and browser-compatible API transport only. Production cloud deployment and authenticated operator sessions remain blocked by FL-18 and FL-20.

- `HttpFleetApi` now uses `package:http`, whose implementation supports Flutter Android and Web. It retains the original `GET /api/v1/hosts` JSON contract, null/stale state handling, 5-second controller polling and error messages.
- Run `flutter create --platforms=web --project-name fleetluma .` from `mobile/` to generate platform scaffolding; `flutter pub get && flutter test && flutter analyze` then `flutter run -d chrome --dart-define=FLEETLUMA_API_BASE_URL=http://localhost:8000` for local web testing.
- For static bundle: `flutter build web --release --dart-define=FLEETLUMA_API_BASE_URL=https://YOUR-API-HOST`. The output is `mobile/build/web`, uploaded as a CI artifact. **Never include secret values in `--dart-define`**, as browser artifacts are public.
- Web deployments require an actual accessible HTTPS coordinator, a strict CORS allowlist on FastAPI, and authenticated read-only endpoints; these are **NOT** provided by FL-17 alone.
- The existing Android CI job remains active. For Android emulator use `http://10.0.2.2:8000`, and for physical Android use an actual reachable LAN/HTTPS address; web previews must be configured with a different backend origin.
- Browser-web compilation is part of CI. Actual deployed browser-to-backend smoke testing is tracked by FL-20.

This branch intentionally does not create a Vercel project, expose monitoring metrics publicly or change the SQLite backend.
