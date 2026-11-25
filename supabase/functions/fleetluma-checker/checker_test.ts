import { assertEquals, assertRejects, assertThrows } from "jsr:@std/assert@1.0.10";
import { allowedTarget, probe, probePinned, isPublicIpv4, verifyPublicDns } from "./checker.ts";
import { EventEmitter } from "node:events";
import type { ClientRequest } from "node:http";
import type { RequestOptions } from "node:https";

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

Deno.test("Public DNS validates all IPv4 answers and safely permits dual-stack hosts", async () => {
  const target = allowedTarget("https://status.example.test/", allowed);
  let ipv6Requested = false;
  assertEquals(await verifyPublicDns(target, async (_hostname, family) => {
    if (family === "AAAA") {
      ipv6Requested = true;
      return ["::1"];
    }
    return ["8.8.8.8"];
  }), "8.8.8.8");
  assertEquals(ipv6Requested, false);
  await assertRejects(() => verifyPublicDns(target, async () => ["127.0.0.1"]));
  await assertRejects(() => verifyPublicDns(target, async () => ["8.8.8.8", "192.168.1.2"]));
  await assertRejects(() => verifyPublicDns(target, async () => []));
});


Deno.test("IP-pinned TLS requires a verified public address before constructing request", async () => {
  let invoked = false;
  const fake = (() => {
    invoked = true;
    throw new Error("requester must not be invoked");
  }) as unknown as Parameters<typeof probePinned>[3];
  await assertRejects(() =>
    probePinned("https://status.example.test/health", allowed, "127.0.0.1", fake));
  assertEquals(invoked, false);
});

Deno.test("TLS request uses exactly the verified IP and preserves HTTPS hostname checks", async () => {
  let options: RequestOptions | undefined;
  const mock = ((opts: RequestOptions, callback: (response: unknown) => void) => {
    options = opts;
    const request = new EventEmitter() as ClientRequest;
    const socket = new EventEmitter() as unknown as ClientRequest["socket"];
    Object.defineProperty(socket, "remoteAddress", { value: "8.8.8.8" });
    request.end = (() => {
      request.emit("socket", socket);
      (socket as EventEmitter).emit("connect");
      const response = {
        statusCode: 204,
        destroy() { /* no response body consumed */ },
      };
      callback(response);
      return request;
    }) as typeof request.end;
    request.destroy = (() => request) as typeof request.destroy;
    return request;
  }) as unknown as Parameters<typeof probePinned>[3];
  const result = await probePinned(
    "https://status.example.test/health", allowed, "8.8.8.8", mock);
  assertEquals(result.status, "HEALTHY");
  assertEquals(result.http_code, 204);
  assertEquals(options?.hostname, "status.example.test");
  assertEquals(options?.servername, "status.example.test");
  assertEquals(options?.port, 443);
  assertEquals(options?.rejectUnauthorized, true);
  assertEquals(options?.agent, false);
  assertEquals(options?.method, "GET");
  assertEquals(options?.path, "/health");
  assertEquals((options?.headers as Record<string, string> | undefined)?.["Host"], "status.example.test");
  const lookup = options?.lookup;
  if (typeof lookup !== "function") throw new Error("IP-pinning lookup missing");
  let resolved = "";
  lookup("status.example.test", {}, (_err, ip) => {
    resolved = ip as string;
  });
  assertEquals(resolved, "8.8.8.8");
});
