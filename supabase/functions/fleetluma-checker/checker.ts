/** Pure validation/probing for scheduled public HTTP endpoint checks. */
export type CheckResult = {
  checked_at: string;
  status: "HEALTHY" | "UNHEALTHY";
  http_code: number | null;
  latency_ms: number | null;
  failure_kind: "none" | "http_error" | "timeout" | "network_error";
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
    const healthy = response.status >= 200 && response.status < 400;
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
 * IPv6 is conservatively denied for this demo. The DNS-to-connect race still
 * requires separate egress restrictions before internet-facing deployment.
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
): Promise<void> {
  // Fail closed if the resolver is disabled / cannot inspect addresses.
  const ipv4 = await resolver(target.hostname, "A");
  const ipv6 = await resolver(target.hostname, "AAAA");
  if (ipv4.length === 0 || ipv6.length > 0 ||
      ipv4.some((address) => !isPublicIpv4(address))) {
    throw new Error("Public IPv4-only DNS verification failed");
  }
}
