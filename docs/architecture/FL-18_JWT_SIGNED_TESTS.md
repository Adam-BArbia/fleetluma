# FL-18 — JWT verification gate test evidence

- FL-18 authorization scope remains **In Progress** until a signed-in operator
  completes a real hosted browser -> FastAPI -> Supabase smoke test.
- This branch adds cryptographically signed RSA JWT tests (not mocks of
  jwt.decode). The test uses an ephemeral in-memory RSA key and a pinned
  test public-key provider, never real production secrets.
- Assertions include valid signature and permitted operator, disallowed
  subject, wrong role, wrong issuer, expired token and incorrect signing key.
- Cloud browser requires a real Supabase session. Only public client keys
  may appear in the compiled Flutter bundle.
- Current application requires a real Supabase Auth user UUID in the
  server-side operator allowlist before hosting is enabled.
