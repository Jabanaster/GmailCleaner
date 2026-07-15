export type ApiStatus = "checking" | "connected" | "error";

export interface HealthResponse {
  ok: boolean;
}

// ─── Gmail OAuth ───
export interface GmailStatus {
  oauth_configured: boolean;
  connected: boolean;
  email: string | null;
}

export interface GmailProfile {
  email: string;
  messages_total: number;
  threads_total: number;
}

// ─── Scan ───
export interface ScanRun {
  id: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  total_scanned: number;
  total_crap: number;
  total_categorized: number;
  total_trashed: number;
  total_labeled: number;
  total_emails: number;
  dry_run?: boolean;
  error_message: string | null;
}

export interface EmailClassification {
  message_id: string;
  subject: string;
  sender: string;
  category: string | null;
  is_crap: boolean;
  crap_reason: string | null;
  confidence: number;
  action_taken: string;
}

export interface ScanStatus {
  running: boolean;
  email: string | null;
  last_run: ScanRun | null;
  classifications: EmailClassification[];
}

export interface CategoryData {
  category: string;
  count: number;
}

export interface CategoryBreakdown {
  categories: CategoryData[];
  crap_count: number;
}

export interface ScanHistory {
  history: ScanRun[];
}

export interface DeviceSession {
  id: string;
  device_name: string;
  extension_version: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  revoked: boolean;
}

// ─── Recovery ───
export interface RecoveryMessagePreview {
  gmail_message_id: string;
  executed_action: string;
  planned_recovery_action: string;
  recoverable: boolean;
  risk_level: "low" | "high";
  reason: string;
  category: string | null;
  confidence: number;
}

export interface RecoveryPreviewResponse {
  operation_batch_id: number;
  scan_run_id: number;
  dry_run: boolean;
  batch_status: string;
  total_actions: number;
  recoverable_count: number;
  skipped_count: number;
  high_risk_count: number;
  warning_list: string[];
  per_message_preview: RecoveryMessagePreview[];
}

export interface RecoveryExecuteResponse {
  operation_batch_id: number;
  scan_run_id: number;
  attempted: number;
  succeeded: number;
  skipped: number;
  failed: number;
  high_risk_skipped: number;
  warnings: string[];
}


