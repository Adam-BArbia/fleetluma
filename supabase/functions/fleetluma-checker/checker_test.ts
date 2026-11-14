import { assertEquals, assertRejects, assertThrows } from "jsr:@std/assert@1.0.10";
import { allowedTarget, probe } from "./checker.ts";

const allowed = new Set(["status.example.test"]);

Deno.test("Accept approved HTTPS hostname", () => {
  assertEquals(
    allowedTarget("https://status.example.test/health", allowed).pathname,
    "/health",
  );
});

Deno.test("Reject unapproved and private targets", () => {
  for (const target of [
    "http://status.example.test",
    "https://localhost/",
    "https://127.0.0.1/",
    "https://169.254.169.254/",
    "https://status.example.test:8443/",
    "https://evil.example.test",
    "https://status.example.test/health?token=secret",
  ]) {
    assertThrows(() => allowedTarget(target, allowed));
  }
});

Deno.test("Classify successful and failing HTTP status codes", async () => {
  const ok = await probe("https://status.example.test/", allowed,
    (async () => new Response("ok", { status: 200 })) as typeof fetch);
  assertEquals(ok.status, "HEALTHY");
  assertEquals(ok.http_code, 200);
  const failure = await probe("https://status.example.test/", allowed,
    (async () => new Response("unavailable", { status: 503 })) as typeof fetch);
  assertEquals(failure.status, "UNHEALTHY");
  assertEquals(failure.failure_kind, "http_error");
});

Deno.test("Network errors do not masquerade as HEALTHY", async () => {
  const failure = await probe("https://status.example.test/", allowed,
    (async () => { throw new TypeError("network down"); }) as typeof fetch);
  assertEquals(failure.status, "UNHEALTHY");
  assertEquals(failure.http_code, null);
  assertEquals(failure.failure_kind, "network_error");
});
