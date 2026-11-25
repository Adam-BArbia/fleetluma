import { request as httpsRequest } from "node:https";

/** Pure validation/probing for scheduled public HTTP endpoint checks. */
export type CheckResult = {
  checked_at: string;
  status: "HEALTHY" | "UNHEALTHY";
  http_code: number | null;
  latency_ms: number | null;
  failure_kind: "none" | "http_error" | "timeout" | "network_error";
  diagnostic_code?: string;
};

export function allowedTarget(rawUrl: string, allowedHosts: Set<string>): URL {
  const url = new URL(rawUrl);
  const host = url.hostname.toLowerCase();
  if (url.protocol !== "https:" || !host || !allowedHosts.has(host)) {
    throw new Error("Target is not an administrator-approved HTTPS host");
  }
  if (url.port || url.username || url.password || url.hash || url.search) {
    throw new Error("Credentials, query strings, ports and fragments are not permitted");
  }
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host) || host.includes(":")) {
    throw new Error("Direct IP addresses are not permitted in cloud checks");
  }
  return url;
}

export async function probe(
  rawUrl: string,
  allowedHosts: Set<string>,
  fetcher: typeof fetch = fetch,
): Promise<CheckResult> {
  const url = allowedTarget(rawUrl, allowedHosts);
  const started = performance.now();
  const checked_at = new Date().toISOString();
  try {
    const response = await fetcher(url.toString(), {
      method: "GET",
      redirect: "manual",  // never follow target redirects
      signal: AbortSignal.timeout(4000),
      headers: { "User-Agent": "FleetLuma-Checker/0.1" },
    });
    // Redirects are deliberately not followed and never imply a healthy service.
    const healthy = response.status >= 200 && response.status < 300;
    await response.body?.cancel();
    return {
      checked_at, status: healthy ? "HEALTHY" : "UNHEALTHY",
      http_code: response.status,
      latency_ms: Math.max(0, Math.round((performance.now() - started) * 100) / 100),
      failure_kind: healthy ? "none" : "http_error",
    };
  } catch (err) {
    const timeout = err instanceof DOMException && err.name === "TimeoutError";
    return {
      checked_at, status: "UNHEALTHY", http_code: null,
      latency_ms: null, failure_kind: timeout ? "timeout" : "network_error",
    };
  }
}

/** Defense in depth: reject DNS answers in private/special-use IPv4 ranges.
 * IPv6 addresses are never dialed by the IP-pinned HTTPS transport.
 * All returned IPv4 addresses must be public.
 */
export function isPublicIpv4(raw: string): boolean {
  const parts = raw.split(".");
  if (parts.length !== 4 || parts.some((p) => !/^\d{1,3}$/.test(p) ||
      (p.length > 1 && p[0] === "0"))) return false;
  const nums = parts.map(Number);
  if (nums.some((n) => n > 255)) return false;
  const [a, b, c] = nums;
  if (a === 0 || a === 10 || a === 127 || a >= 224 ||
      a === 169 && b === 254 || a === 172 && b >= 16 && b <= 31 ||
      a === 192 && b === 168 || a === 100 && b >= 64 && b <= 127 ||
      a === 192 && b === 0 && c === 0 ||
      a === 192 && b === 0 && c === 2 ||
      a === 198 && (b === 18 || b === 19 || b === 51 && c === 100) ||
      a === 203 && b === 0 && c === 113) return false;
  return true;
}

export async function verifyPublicDns(
  target: URL,
  resolver: (hostname: string, family: "A" | "AAAA") => Promise<string[]> =
    async (hostname, family) => Deno.resolveDns(hostname, family),
): Promise<string> {
  // Fail closed if the resolver is disabled / cannot inspect addresses.
  // Only IPv4 is used by the pinned TLS transport. An AAAA record is
  // harmless because the request cannot connect to it.
  const ipv4 = await resolver(target.hostname, "A");
  if (ipv4.length === 0 ||
      ipv4.some((address) => !isPublicIpv4(address))) {
    throw new Error("Public IPv4 DNS verification failed");
  }
  // Return the verified IP. The TLS connection must not re-resolve the host.
  return ipv4[0];
}

/**
 * Safe HTTPS status probe, pinning the connection to a prevalidated public IP.
 * Node's TLS client retains hostname-based SNI/certificate verification;
 * lookup never resolves the hostname again. No redirects or response bodies.
 */
export async function probePinned(
  rawUrl: string,
  allowedHosts: Set<string>,
  verifiedIp: string,
  requester: typeof httpsRequest = httpsRequest,
): Promise<CheckResult> {
  const url = allowedTarget(rawUrl, allowedHosts);
  if (!isPublicIpv4(verifiedIp)) {
    throw new Error("Refusing a non-public pinned destination");
  }
  const started = performance.now();
  const checked_at = new Date().toISOString();
  return await new Promise<CheckResult>((resolve) => {
    let settled = false;
    let timedOut = false;
    // Only a stable allowlisted category may leave the secret-protected
    // checker; never return raw errors, host IPs, certificates or URLs.
    let diagnosticCode: string | undefined;
    let request: ReturnType<typeof httpsRequest> | undefined;
    const finish = (
      status: number | null,
      failure: CheckResult["failure_kind"],
    ) => {
      if (settled) return;
      settled = true;
      clearTimeout(deadline);
      const healthy = status !== null && status >= 200 && status < 300;
      resolve({
        checked_at,
        status: healthy ? "HEALTHY" : "UNHEALTHY",
        http_code: status,
        latency_ms: status === null ? null :
          Math.max(0, Math.round((performance.now() - started) * 100) / 100),
        failure_kind: healthy ? "none" :
          status === null ? failure : "http_error",
        diagnostic_code: status === null ? diagnosticCode : undefined,
      });
    };
    const deadline = setTimeout(() => {
      timedOut = true;
      request?.destroy(new Error("Checker request deadline reached"));
      finish(null, "timeout");
    }, 4000);
    try {
      request = requester({
        hostname: url.hostname,
        servername: url.hostname,
        port: 443,
        method: "GET",
        path: url.pathname,
        agent: false,
        rejectUnauthorized: true,
        timeout: 4000,
        headers: {
          "Host": url.hostname,
          "User-Agent": "FleetLuma-Checker/0.1",
          "Connection": "close",
          "Accept": "*/*",
        },
        lookup: (hostname, _options, callback) => {
          if (hostname.toLowerCase() !== url.hostname) {
            callback(new Error("Unapproved DNS hostname"), "", 4);
            return;
          }
          callback(null, verifiedIp, 4);
        },
      }, (response) => {
        const code = response.statusCode;
        response.destroy();
        finish(typeof code === "number" && code >= 100 && code <= 599
          ? code : null, "network_error");
      });
      request.on("socket", (socket) => {
        socket.once("connect", () => {
          if (socket.remoteAddress !== verifiedIp) {
            diagnosticCode = "SOCKET_IP_MISMATCH";
            request?.destroy(new Error("Connected IP differs from verified IP"));
          }
        });
      });
      request.on("timeout", () => {
        timedOut = true;
        request?.destroy(new Error("Checker request timed out"));
      });
      request.on("error", (error: Error & { code?: string }) => {
        const code = error.code ?? "";
        const recognized = new Set([
          "EACCES", "EPERM", "ECONNREFUSED", "ECONNRESET", "ETIMEDOUT",
          "ENETUNREACH", "EHOSTUNREACH", "ENOTFOUND",
          "ERR_TLS_CERT_ALTNAME_INVALID", "ERR_INVALID_ARG_TYPE",
          "ERR_INVALID_PROTOCOL", "ERR_UNSUPPORTED_ESM_URL_SCHEME",
        ]);
        diagnosticCode ??= recognized.has(code) ? code : "OTHER_NETWORK_ERROR";
        finish(null, timedOut ? "timeout" : "network_error");
      });
      request.end();
    } catch {
      diagnosticCode = "REQUEST_SETUP_ERROR";
      request?.destroy();
      finish(null, "network_error");
    }
  });
}
