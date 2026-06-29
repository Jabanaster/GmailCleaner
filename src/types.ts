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
