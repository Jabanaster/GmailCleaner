import { backend, BackendError } from "./backend-client";
import { clearBackendCredentials, getBackendAccessToken, getBackendRefreshToken, setBackendAccessToken, setBackendRefreshToken } from "./chrome-storage";
import type { BackendAuthStatus, BackendSessionInfo } from "./types";

export async function pairBackend(pairingCode: string, deviceName: string): Promise<BackendAuthStatus> {
  const code = pairingCode.trim().toUpperCase();
  if (!/^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) throw new Error("Pairing code must use the format ABCD-EFGH");
  if (!deviceName.trim() || deviceName.length > 100) throw new Error("Enter a device name of 1–100 characters");
  const credentials = await backend.pair(code, deviceName.trim(), chrome.runtime.getManifest().version);
  if (!credentials.access_token || !credentials.refresh_token) throw new BackendError("Backend returned incomplete session credentials", "server");
  await Promise.all([setBackendAccessToken(credentials.access_token), setBackendRefreshToken(credentials.refresh_token)]);
  return getBackendAuthStatus();
}

export async function refreshBackendSession(): Promise<string> {
  const refreshToken = await getBackendRefreshToken();
  if (!refreshToken) throw new BackendError("Organizer session has expired", "authentication", 401);
  try {
    const rotated = await backend.refresh(refreshToken);
    if (!rotated.access_token || !rotated.refresh_token) throw new BackendError("Backend returned incomplete rotated credentials", "server");
    await Promise.all([setBackendAccessToken(rotated.access_token), setBackendRefreshToken(rotated.refresh_token)]);
    return rotated.access_token;
  } catch (error) {
    await clearBackendCredentials();
    throw error;
  }
}

export async function withBackendAuth<T>(request: (accessToken: string) => Promise<T>): Promise<T> {
  let token = await getBackendAccessToken();
  if (!token) token = await refreshBackendSession();
  try { return await request(token); }
  catch (error) {
    if (!(error instanceof BackendError) || error.status !== 401) throw error;
    const refreshed = await refreshBackendSession();
    return request(refreshed); // Exactly one retry. A second 401 is returned to the caller.
  }
}

export async function getBackendAuthStatus(): Promise<BackendAuthStatus> {
  const hasRefresh = Boolean(await getBackendRefreshToken());
  if (!hasRefresh) return { state: "unpaired" };
  try {
    const session = await withBackendAuth((token) => backend.me<BackendSessionInfo>(token));
    return { state: "paired", session };
  } catch (error) {
    if (error instanceof BackendError && ["network", "timeout", "server"].includes(error.kind)) return { state: "unavailable", error: error.message };
    return { state: "expired", error: "Organizer session expired. Pair this device again." };
  }
}

export async function disconnectBackend(): Promise<void> {
  const token = await getBackendAccessToken();
  try { if (token) await backend.revoke(token); }
  finally { await clearBackendCredentials(); }
}
