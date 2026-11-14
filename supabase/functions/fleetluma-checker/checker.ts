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
