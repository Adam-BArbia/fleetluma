/** FL-19: restricted Supabase Edge Function invoked by named-key Cron only. */
import { withSupabase } from "npm:@supabase/server@1.9.2";
import postgres from "npm:postgres@3.4.7";
import { allowedTarget, probe, verifyPublicDns } from "./checker.ts";

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
        await verifyPublicDns(target);
        const result = await probe(service.url, allowed);
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
    // Enforce 24-hour maximum history for the demo, independently of API requests.
    await sql`DELETE FROM fleetluma.samples WHERE received_at < NOW() - INTERVAL '24 hours'`;
    await sql`DELETE FROM fleetluma.service_checks WHERE checked_at < NOW() - INTERVAL '24 hours'`;
    return respond(200, { checked, skipped });
  } catch (_err) {
    return respond(500, { error: "Scheduled checker unavailable" });
  } finally {
    await sql.end({ timeout: 3 });
  }
  }),
};
