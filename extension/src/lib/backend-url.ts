const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function normalizeBackendUrl(input: string): string {
  let url: URL;
  try { url = new URL(input.trim()); }
  catch { throw new Error("Backend URL is invalid"); }
  if (url.username || url.password || url.search || url.hash) throw new Error("Backend URL must not contain credentials, query parameters, or a fragment");
  if (url.pathname !== "/") throw new Error("Backend URL must not contain a path");
  if (url.protocol !== "https:" && !(url.protocol === "http:" && LOOPBACK_HOSTS.has(url.hostname))) {
    throw new Error("Backend URL must use HTTPS; HTTP is allowed only for localhost development");
  }
  return url.origin;
}

export function isLocalDevelopmentUrl(input: string): boolean {
  const url = new URL(normalizeBackendUrl(input));
  return url.protocol === "http:" && LOOPBACK_HOSTS.has(url.hostname);
}
