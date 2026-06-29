import { backend } from "./lib/backend-client";
import { disconnectBackend, getBackendAuthStatus, pairBackend, refreshBackendSession, withBackendAuth } from "./lib/backend-auth";
import { getLatestScan, getSettings, patchSettings, saveLatestScan } from "./lib/chrome-storage";
import { getMessage, listLabels, listMessages } from "./lib/gmail-api";
import { isRuntimeMessage } from "./lib/messaging";
import type { GmailMessageSummary, GoogleProfile, RuntimeMessage, RuntimeResponse, ScanJobStatus } from "./lib/types";

async function getToken(interactive = false): Promise<string> {
  const result = await chrome.identity.getAuthToken({ interactive });
  if (!result.token) throw new Error("Google authorization did not return an access token");
  return result.token;
}

async function clearToken(): Promise<void> {
  const result = await chrome.identity.getAuthToken({ interactive: false });
  if (result.token) await chrome.identity.removeCachedAuthToken({ token: result.token });
}

async function getProfile(interactive = false): Promise<GoogleProfile> {
  const token = await getToken(interactive);
  const response = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/profile", {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error(`Gmail profile request returned ${response.status}`);
  const profile = (await response.json()) as { emailAddress: string };
  return { email: profile.emailAddress };
}

async function previewInbox(limit?: number): Promise<ScanJobStatus> {
  const settings = await getSettings();
  const scanLimit = Math.min(Math.max(limit ?? settings.scanLimit, 1), 50);
  const running: ScanJobStatus = {
    state: "running",
    processed: 0,
    total: scanLimit,
    proposals: [],
    updatedAt: new Date().toISOString()
  };
  await saveLatestScan(running);

  try {
    const token = await getToken(true);
    const refs = await listMessages(token, scanLimit);
    const messages: GmailMessageSummary[] = [];
    for (const ref of refs) messages.push(await getMessage(token, ref.id));

    // Classification remains exclusively behind the FastAPI boundary.
    const result = await withBackendAuth((accessToken) => backend.classifyPreview<{ jobId?: string; proposals?: ScanJobStatus["proposals"] }>(accessToken, messages));
    const completed: ScanJobStatus = {
      jobId: result.jobId,
      state: "completed",
      processed: messages.length,
      total: messages.length,
      proposals: result.proposals ?? [],
      updatedAt: new Date().toISOString()
    };
    await saveLatestScan(completed);
    await patchSettings({ lastScanAt: completed.updatedAt });
    return completed;
  } catch (error) {
    const failed: ScanJobStatus = {
      ...running,
      state: "failed",
      error: error instanceof Error ? error.message : "Scan failed",
      updatedAt: new Date().toISOString()
    };
    await saveLatestScan(failed);
    throw error;
  }
}

async function route(message: RuntimeMessage): Promise<unknown> {
  switch (message.type) {
    case "auth:getToken": return getToken(message.interactive);
    case "auth:clearToken": return clearToken();
    case "auth:getProfile": return getProfile(message.interactive);
    case "gmail:listMessages": return listMessages(await getToken(true), message.limit ?? 25);
    case "gmail:getMessage": return getMessage(await getToken(true), message.messageId);
    case "gmail:listLabels": return listLabels(await getToken(true));
    case "scan:previewInbox": return previewInbox(message.limit);
    case "scan:getLatest": return getLatestScan();
    case "backend:pair": return pairBackend(message.pairingCode, message.deviceName);
    case "backend:authStatus": return getBackendAuthStatus();
    case "backend:refresh": await refreshBackendSession(); return getBackendAuthStatus();
    case "backend:disconnect": return disconnectBackend();
    case "backend:openDashboard": {
      const { backendBaseUrl } = await getSettings();
      await chrome.tabs.create({ url: backendBaseUrl });
      return undefined;
    }
    case "backend:health": return backend.health();
    case "sidepanel:open": {
      const window = await chrome.windows.getLastFocused();
      if (window.id == null) throw new Error("No browser window is available");
      await chrome.sidePanel.open({ windowId: window.id });
      return undefined;
    }
  }
}

chrome.runtime.onInstalled.addListener(() => {
  void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });
});

chrome.runtime.onMessage.addListener((message: unknown, _sender, sendResponse: (response: RuntimeResponse) => void) => {
  if (!isRuntimeMessage(message)) return false;
  void route(message)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error: unknown) => sendResponse({ ok: false, error: error instanceof Error ? error.message : "Unknown extension error" }));
  return true;
});
