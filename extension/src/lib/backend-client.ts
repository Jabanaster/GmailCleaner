import { getSettings } from "./chrome-storage";
import { normalizeBackendUrl } from "./backend-url";

const REQUEST_TIMEOUT_MS = 15_000;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;

export type BackendFailureKind = "timeout" | "network" | "authentication" | "authorization" | "validation" | "server" | "response_too_large";

export class BackendError extends Error {
  constructor(message: string, public readonly kind: BackendFailureKind, public readonly status?: number) {
    super(message);
    this.name = "BackendError";
  }
}

export interface PairResponse { access_token: string; refresh_token: string }
export interface RefreshResponse { access_token: string; refresh_token: string }

type RequestOptions = { method?: "GET" | "POST"; body?: unknown; accessToken?: string };

function failureForStatus(status: number): BackendFailureKind {
  if (status === 401) return "authentication";
  if (status === 403) return "authorization";
  if (status === 400 || status === 409 || status === 415 || status === 422 || status === 429) return "validation";
  return "server";
}

export async function backendRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { backendBaseUrl } = await getSettings();
  const baseUrl = normalizeBackendUrl(backendBaseUrl);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(options.accessToken ? { Authorization: `Bearer ${options.accessToken}` } : {})
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal
    });
    const contentLength = Number(response.headers.get("content-length") ?? 0);
    if (contentLength > MAX_RESPONSE_BYTES) throw new BackendError("Backend response exceeded the allowed size", "response_too_large");
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > MAX_RESPONSE_BYTES) throw new BackendError("Backend response exceeded the allowed size", "response_too_large");
    if (!response.ok) throw new BackendError(`Backend request failed (${response.status})`, failureForStatus(response.status), response.status);
    if (!text) return undefined as T;
    try { return JSON.parse(text) as T; }
    catch { throw new BackendError("Backend returned an invalid JSON response", "server", response.status); }
  } catch (error) {
    if (error instanceof BackendError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw new BackendError("Backend request timed out", "timeout");
    throw new BackendError("Backend is unavailable", "network");
  } finally { clearTimeout(timeout); }
}

export const backend = {
  health: () => backendRequest<unknown>("/health"),
  pair: (pairingCode: string, deviceName: string, extensionVersion: string) => backendRequest<PairResponse>("/api/extension/pair", { method: "POST", body: { pairing_code: pairingCode, device_name: deviceName, extension_version: extensionVersion } }),
  refresh: (refreshToken: string) => backendRequest<RefreshResponse>("/api/extension/auth/refresh", { method: "POST", body: { refresh_token: refreshToken } }),
  me: <T>(token: string) => backendRequest<T>("/api/extension/auth/me", { accessToken: token }),
  revoke: (token: string) => backendRequest<void>("/api/extension/auth/revoke", { method: "POST", accessToken: token }),
  classifyPreview: <T>(token: string, messages: unknown[]) => backendRequest<T>("/api/extension/classify-preview", { method: "POST", accessToken: token, body: { messages } })
};
