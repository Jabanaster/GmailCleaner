import type { ExtensionSettings, ScanJobStatus } from "./types";
import { normalizeBackendUrl } from "./backend-url";

export const DEFAULT_SETTINGS: ExtensionSettings = {
  backendBaseUrl: "http://localhost:5273",
  scanLimit: 25,
  dryRunMode: true,
  lastScanAt: null
};

const SETTINGS_KEY = "settings";
const LATEST_SCAN_KEY = "latestScan";
const ACCESS_TOKEN_KEY = "backendAccessToken";
const REFRESH_TOKEN_KEY = "backendRefreshToken";

export async function getSettings(): Promise<ExtensionSettings> {
  const stored = await chrome.storage.local.get(SETTINGS_KEY);
  return { ...DEFAULT_SETTINGS, ...(stored[SETTINGS_KEY] as Partial<ExtensionSettings> | undefined) };
}

export async function saveSettings(settings: ExtensionSettings): Promise<void> {
  const previous = await getSettings();
  const normalized = { ...settings, backendBaseUrl: normalizeBackendUrl(settings.backendBaseUrl) };
  if (normalizeBackendUrl(previous.backendBaseUrl) !== normalized.backendBaseUrl) await clearBackendCredentials();
  await chrome.storage.local.set({ [SETTINGS_KEY]: normalized });
}

export async function patchSettings(patch: Partial<ExtensionSettings>): Promise<ExtensionSettings> {
  const settings = { ...(await getSettings()), ...patch };
  await saveSettings(settings);
  return settings;
}

export async function getLatestScan(): Promise<ScanJobStatus | null> {
  const stored = await chrome.storage.local.get(LATEST_SCAN_KEY);
  return (stored[LATEST_SCAN_KEY] as ScanJobStatus | undefined) ?? null;
}

export async function saveLatestScan(scan: ScanJobStatus): Promise<void> {
  await chrome.storage.local.set({ [LATEST_SCAN_KEY]: scan });
}

// These credential helpers are consumed only by the service worker's auth module.
export async function getBackendAccessToken(): Promise<string | null> {
  return (await chrome.storage.session.get(ACCESS_TOKEN_KEY))[ACCESS_TOKEN_KEY] as string | undefined ?? null;
}

export async function setBackendAccessToken(token: string): Promise<void> {
  await chrome.storage.session.set({ [ACCESS_TOKEN_KEY]: token });
}

export async function getBackendRefreshToken(): Promise<string | null> {
  return (await chrome.storage.local.get(REFRESH_TOKEN_KEY))[REFRESH_TOKEN_KEY] as string | undefined ?? null;
}

export async function setBackendRefreshToken(token: string): Promise<void> {
  await chrome.storage.local.set({ [REFRESH_TOKEN_KEY]: token });
}

export async function clearBackendCredentials(): Promise<void> {
  await Promise.all([chrome.storage.session.remove(ACCESS_TOKEN_KEY), chrome.storage.local.remove(REFRESH_TOKEN_KEY)]);
}
