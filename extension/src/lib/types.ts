export interface GmailMessageSummary {
  id: string;
  threadId: string;
  subject: string;
  from: string;
  receivedAt?: string;
  snippet: string;
  labelIds: string[];
}

export interface ClassificationProposal {
  messageId: string;
  proposedLabel: string;
  confidence: number;
  reason?: string;
}

export type ScanState = "idle" | "queued" | "running" | "completed" | "failed";

export interface ScanJobStatus {
  jobId?: string;
  state: ScanState;
  processed: number;
  total: number;
  proposals: ClassificationProposal[];
  error?: string;
  updatedAt: string;
}

export interface ExtensionSettings {
  backendBaseUrl: string;
  scanLimit: number;
  dryRunMode: boolean;
  lastScanAt: string | null;
}

export type BackendConnectionState = "unpaired" | "paired" | "expired" | "unavailable";

export interface BackendSessionInfo {
  user: { id: string; displayName?: string };
  deviceSessionId: string;
  deviceName: string;
  scopes: string[];
  accessTokenExpiresAt: string;
  environment: string;
}

export interface BackendAuthStatus {
  state: BackendConnectionState;
  session?: BackendSessionInfo;
  error?: string;
}

export interface GoogleProfile {
  email: string;
  name?: string;
  picture?: string;
}

export type RuntimeMessage =
  | { type: "auth:getToken"; interactive?: boolean }
  | { type: "auth:clearToken" }
  | { type: "auth:getProfile"; interactive?: boolean }
  | { type: "gmail:listMessages"; limit?: number }
  | { type: "gmail:getMessage"; messageId: string }
  | { type: "gmail:listLabels" }
  | { type: "scan:previewInbox"; limit?: number }
  | { type: "scan:getLatest" }
  | { type: "backend:pair"; pairingCode: string; deviceName: string }
  | { type: "backend:authStatus" }
  | { type: "backend:refresh" }
  | { type: "backend:disconnect" }
  | { type: "backend:openDashboard" }
  | { type: "backend:health" }
  | { type: "sidepanel:open" };

export interface RuntimeResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}
