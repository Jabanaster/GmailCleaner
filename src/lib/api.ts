import type { GmailStatus, GmailProfile, ScanStatus, ScanHistory, CategoryBreakdown, DeviceSession, RecoveryPreviewResponse, RecoveryExecuteResponse } from "@/types";


export const api = {
  getGmailStatus: async (): Promise<GmailStatus> => {
    const res = await fetch("/api/gmail/status");
    if (!res.ok) throw new Error("API unreachable");
    return res.json();
  },

  getGmailProfile: async (): Promise<GmailProfile> => {
    const res = await fetch("/api/gmail/profile");
    if (!res.ok) throw new Error("Failed to load profile");
    return res.json();
  },

  getScanStatus: async (): Promise<ScanStatus> => {
    const res = await fetch("/api/scan/status");
    if (!res.ok) throw new Error("Failed to load scan status");
    return res.json();
  },

  getScanHistory: async (): Promise<ScanHistory> => {
    const res = await fetch("/api/scan/history");
    if (!res.ok) throw new Error("Failed to load scan history");
    return res.json();
  },

  getScanCategories: async (): Promise<CategoryBreakdown> => {
    const res = await fetch("/api/scan/categories");
    if (!res.ok) throw new Error("Failed to load categories");
    return res.json();
  },

  getDevices: async (): Promise<DeviceSession[]> => {
    const res = await fetch("/api/extension/devices");
    if (!res.ok) throw new Error("Failed to fetch devices");
    const data = await res.json();
    return data.devices ?? [];
  },

  startOAuth: async (): Promise<{ auth_url: string }> => {
    const res = await fetch("/api/gmail/oauth/start");
    if (!res.ok) throw new Error("Failed to start OAuth");
    return res.json();
  },

  disconnectGmail: async (): Promise<void> => {
    const res = await fetch("/api/gmail/disconnect", { method: "POST" });
    if (!res.ok) throw new Error("Failed to disconnect");
  },

  startScan: async (dryRun: boolean): Promise<{ detail?: string }> => {
    const res = await fetch(`/api/scan/start?dry_run=${dryRun}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to start scan");
    }
    return data;
  },

  createPairingCode: async (): Promise<{ pairing_code: string; expires_at: string }> => {
    const res = await fetch("/api/extension/pairing-codes", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Could not create pairing code");
    }
    return data;
  },

  revokeDevice: async (deviceId: string): Promise<void> => {
    const res = await fetch(`/api/extension/devices/${deviceId}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      throw new Error("Could not revoke device");
    }
  },

  getRecoveryPreview: async (params: { operation_batch_id?: number; scan_run_id?: number }): Promise<RecoveryPreviewResponse> => {
    const res = await fetch("/api/recovery/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || "Failed to load recovery preview");
    }
    return data;
  },

  executeRecovery: async (params: {
    operation_batch_id?: number;
    scan_run_id?: number;
    confirm_execute: boolean;
    handle_high_risk?: boolean;
  }): Promise<RecoveryExecuteResponse> => {
    const res = await fetch("/api/recovery/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || "Failed to execute recovery");
    }
    return data;
  },
};

