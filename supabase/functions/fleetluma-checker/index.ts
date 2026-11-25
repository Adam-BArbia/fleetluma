/** FL-19: restricted Supabase Edge Function invoked by named-key Cron only. */
import { withSupabase } from "npm:@supabase/server@1.9.2";
import postgres from "npm:postgres@3.4.7";
import { allowedTarget, probePinned, verifyPublicDns } from "./checker.ts";

const respond = (status: number, body: object) =>
  new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json" },
  });

// Service-to-service caller authentication is enforced by the Supabase
// wrapper: ONLY the named secret key "fleetluma-checker" can call this worker.
// Hosted configuration MUST set verify_jwt=false for apikey-secret mode.
// The secret is supplied on apikey, never in the function source or URL.
// No anonymous access: auth:'secret:<name>' fails closed before this handler.
export default {
  fetch: withSupabase({ auth: "secret:fleetluma-checker" }, async (request) => {
    if (request.method !== "POST") {
      return respond(405, { error: "Method not allowed" });
    }
  // Supabase injects SUPABASE_DB_URL into hosted Edge Functions.
  // An explicit restricted pooler DSN still takes priority when configured.
  const databaseUrl = Deno.env.get("FLEETLUMA_DB_URL") ??
    Deno.env.get("SUPABASE_DB_URL") ?? "";
  const hosts = (Deno.env.get("FLEETLUMA_CHECK_ALLOWED_HOSTS") ?? "")
    .split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
  if (!databaseUrl || hosts.length === 0 || Deno.env.get("FLEETLUMA_PUBLIC_PROBES_ENABLED") !== "true") {
    return respond(503, { error: "Checker is not configured" });
  }
  const allowed = new Set(hosts);
  // A single short-lived pooler connection, never available to browser clients.
  const sql = postgres(databaseUrl, { max: 1, prepare: false, ssl: "require" });
  try {
    const services = await sql<
      { id: string; url: string }[]
    >`SELECT id, url FROM fleetluma.services WHERE enabled=true ORDER BY name LIMIT 10`;
    let checked = 0;
    let skipped = 0;
    for (const service of services) {
      try {
        const target = allowedTarget(service.url, allowed);
        const verifiedIp = await verifyPublicDns(target);
        // IP-pinned HTTPS with original hostname SNI + cert verification.
        const result = await probePinned(service.url, allowed, verifiedIp);
        await sql`INSERT INTO fleetluma.service_checks
          (service_id, checked_at, status, http_code, latency_ms, failure_kind)
          VALUES
          (${service.id}, ${result.checked_at}, ${result.status},
           ${result.http_code}, ${result.latency_ms}, ${result.failure_kind})`;
        checked++;
      } catch (_err) {
        // A service's misconfiguration must not crash checks for others.
        skipped++;
      }
    }
    // FL-36: independent pg_cron retention runs without a network request.
    // Do not couple retention to the optional HTTP checker lifecycle.
    return respond(200, { checked, skipped });
  } catch (_err) {
    return respond(500, { error: "Scheduled checker unavailable" });
  } finally {
    await sql.end({ timeout: 3 });
  }
  }),
};
