import { assertEquals, assertRejects, assertThrows } from "jsr:@std/assert@1.0.10";
import { allowedTarget, probe, isPublicIpv4, verifyPublicDns } from "./checker.ts";

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

Deno.test("Redirects are never followed and never reported as healthy", async () => {
  let redirectMode: RequestRedirect | undefined;
  const result = await probe("https://status.example.test/health", allowed,
    (async (_input: URL | RequestInfo, init?: RequestInit) => {
      redirectMode = init?.redirect;
      return new Response(null, {
        status: 302, headers: { Location: "http://127.0.0.1/admin" },
      });
    }) as typeof fetch);
  assertEquals(redirectMode, "manual");
  assertEquals(result.status, "UNHEALTHY");
  assertEquals(result.http_code, 302);
  assertEquals(result.failure_kind, "http_error");
});

Deno.test("Network errors do not masquerade as HEALTHY", async () => {
  const failure = await probe("https://status.example.test/", allowed,
    (async () => { throw new TypeError("network down"); }) as typeof fetch);
  assertEquals(failure.status, "UNHEALTHY");
  assertEquals(failure.http_code, null);
  assertEquals(failure.failure_kind, "network_error");
});

Deno.test("Private, metadata and special IPv4 addresses are rejected", () => {
  for (const ip of ["127.0.0.1", "10.4.5.6", "192.168.1.2",
    "172.16.1.1", "169.254.169.254", "100.64.0.1",
    "0.0.0.0", "198.18.0.1", "203.0.113.10", "255.255.255.255"]) {
    assertEquals(isPublicIpv4(ip), false);
  }
  assertEquals(isPublicIpv4("8.8.8.8"), true);
});

Deno.test("Public DNS verification rejects private and IPv6 answers", async () => {
  const target = allowedTarget("https://status.example.test/", allowed);
  await verifyPublicDns(target, async (_hostname, family) =>
    family === "A" ? ["8.8.8.8"] : []);
  await assertRejects(() => verifyPublicDns(target, async (_hostname, family) =>
    family === "A" ? ["127.0.0.1"] : []));
  await assertRejects(() => verifyPublicDns(target, async (_hostname, family) =>
    family === "A" ? ["8.8.8.8"] : ["::1"]));
});
