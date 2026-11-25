import { allowedTarget, isPublicIpv4, type CheckResult } from "./checker.ts";

/**
 * IP-pinned HTTPS probe using the native Deno TLS primitives.
 *
 * The DNS A response is validated separately. Deno.connect dials ONLY that
 * public IPv4 address. Deno.startTls wraps the existing socket with the
 * original hostname for SNI and CA/hostname certificate validation.
 * No hostname-based re-resolution, proxy, redirects, or response bodies.
 */
export async function probePinnedNative(
  rawUrl: string,
  approvedHosts: Set<string>,
  verifiedIp: string,
): Promise<CheckResult> {
  const target = allowedTarget(rawUrl, approvedHosts);
  if (!isPublicIpv4(verifiedIp)) {
    throw new Error("Refusing non-public pinned IP");
  }
  const checked_at = new Date().toISOString();
  const started = performance.now();
  let tcp: Deno.TcpConn | undefined;
  let tls: Deno.TlsConn | undefined;
  let expired = false;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  const stop = () => {
    try { tls?.close(); } catch { /* already closed */ }
    try { tcp?.close(); } catch { /* ownership moved to TLS */ }
  };
  const doProbe = async (): Promise<number> => {
    // Always dial the verified IP, NEVER the user-supplied hostname.
    tcp = await Deno.connect({ hostname: verifiedIp, port: 443 });
    if (expired) { stop(); throw new Error("Probe expired"); }

    // The hostname is used only for TLS SNI and certificate validation.
    tls = await Deno.startTls(tcp, { hostname: target.hostname });
    if (expired) { stop(); throw new Error("Probe expired"); }
    const request = new TextEncoder().encode(
      `GET ${target.pathname} HTTP/1.1\r\nHost: ${target.hostname}\r\nUser-Agent: FleetLuma-Checker/0.1\r\nAccept: */*\r\nConnection: close\r\n\r\n`,
    );
    let written = 0;
    while (written < request.length) {
      const n = await tls.write(request.subarray(written));
      if (n <= 0) throw new Error("TLS write failed");
      written += n;
    }
    const buffer = new Uint8Array(1024);
    const n = await tls.read(buffer);
    if (n === null || n === 0) throw new Error("No HTTP response");
    const firstLine = new TextDecoder().decode(buffer.subarray(0, n))
      .split("\r\n", 1)[0];
    const match = /^HTTP\/1\.[01]\s+([1-5]\d{2})(?:\s|$)/.exec(firstLine);
    if (!match) throw new Error("Invalid HTTP status line");
    return Number(match[1]);
  };
  try {
    const deadline = new Promise<never>((_, reject) => {
      timeout = setTimeout(() => {
        expired = true;
        stop();
        reject(new Error("Probe timed out"));
      }, 4000);
    });
    const code = await Promise.race([doProbe(), deadline]);
    const healthy = code >= 200 && code < 300;
    return {
      checked_at,
      status: healthy ? "HEALTHY" : "UNHEALTHY",
      http_code: code,
      latency_ms: Math.max(0, Math.round((performance.now() - started) * 100) / 100),
      failure_kind: healthy ? "none" : "http_error",
    };
  } catch (error) {
    // Only safe categories are returned to the private, named-key caller.
    return {
      checked_at,
      status: "UNHEALTHY",
      http_code: null,
      latency_ms: null,
      failure_kind: expired ? "timeout" : "network_error",
      diagnostic_code: expired ? "NATIVE_TLS_TIMEOUT"
        : error instanceof Deno.errors.PermissionDenied ? "NATIVE_PERMISSION"
        : "NATIVE_TLS_ERROR",
    };
  } finally {
    if (timeout !== undefined) clearTimeout(timeout);
    stop();
  }
}
