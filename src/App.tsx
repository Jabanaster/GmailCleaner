import type {
  GmailStatus,
  GmailProfile,
  ScanStatus,
  ScanHistory,
  CategoryBreakdown,
  EmailClassification,
} from "./types";
import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Mail,
  Trash2,
  Tag,
  Play,
  RefreshCw,
  Unlink,
  Loader2,
  CheckCircle2,
  XCircle,
  Inbox,
  AlertTriangle,
  History,
  BarChart3,
  Sparkles,
  KeyRound,
  Monitor,
  Moon,
  Sun,
  Shield,
  ShieldOff,
  Clock,
  Cpu,
  X,
} from "lucide-react";

// ─── Color palette ───────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  work:        { bg: "hsl(217 91% 95%)", text: "hsl(217 91% 40%)", bar: "hsl(217 91% 60%)" },
  finance:     { bg: "hsl(142 71% 93%)", text: "hsl(142 71% 30%)", bar: "hsl(142 71% 45%)" },
  personal:    { bg: "hsl(280 65% 94%)", text: "hsl(280 65% 40%)", bar: "hsl(280 65% 60%)" },
  travel:      { bg: "hsl(33 100% 93%)", text: "hsl(33 100% 35%)", bar: "hsl(33 100% 50%)" },
  receipts:    { bg: "hsl(190 90% 93%)", text: "hsl(190 90% 30%)", bar: "hsl(190 90% 45%)" },
  social:      { bg: "hsl(340 75% 94%)", text: "hsl(340 75% 40%)", bar: "hsl(340 75% 55%)" },
  newsletters: { bg: "hsl(45 93% 93%)",  text: "hsl(45 93% 30%)",  bar: "hsl(45 93% 47%)"  },
  promotions:  { bg: "hsl(265 80% 94%)", text: "hsl(265 80% 40%)", bar: "hsl(265 80% 60%)" },
};

const CATEGORY_LABELS: Record<string, string> = {
  work: "Work", finance: "Finance", personal: "Personal", travel: "Travel",
  receipts: "Receipts", social: "Social", newsletters: "Newsletters", promotions: "Promotions",
};

const CATEGORY_ICONS: Record<string, string> = {
  work: "💼", finance: "💰", personal: "👤", travel: "✈️",
  receipts: "🧾", social: "🌐", newsletters: "📰", promotions: "🏷️",
};

// ─── Dark mode hook ───────────────────────────────────────────────────────────

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("gmail-cleaner-dark");
    if (saved !== null) return saved === "true";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    localStorage.setItem("gmail-cleaner-dark", String(dark));
  }, [dark]);

  return [dark, setDark] as const;
}

// ─── Device type ─────────────────────────────────────────────────────────────

interface DeviceSession {
  id: string;
  device_name: string;
  extension_version: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  revoked: boolean;
}

// ─── App ─────────────────────────────────────────────────────────────────────

function App() {
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [profile, setProfile] = useState<GmailProfile | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [history, setHistory] = useState<ScanHistory | null>(null);
  const [categories, setCategories] = useState<CategoryBreakdown | null>(null);
  const [devices, setDevices] = useState<DeviceSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pairingCode, setPairingCode] = useState<{ code: string; expiresAt: string } | null>(null);
  const [pairingModalOpen, setPairingModalOpen] = useState(false);
  const [pairingCountdown, setPairingCountdown] = useState(0);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [dark, setDark] = useDarkMode();
  const { toast } = useToast();

  const fetchStatus = useCallback(async () => {
    try {
      const statusRes = await fetch("/api/gmail/status");
      if (!statusRes.ok) throw new Error("API unreachable");
      const status: GmailStatus = await statusRes.json();
      setGmailStatus(status);
      setError(null);

      if (status.connected) {
        const [profileRes, scanRes, histRes, catRes] = await Promise.all([
          fetch("/api/gmail/profile").catch(() => null),
          fetch("/api/scan/status"),
          fetch("/api/scan/history"),
          fetch("/api/scan/categories"),
        ]);

        if (profileRes?.ok) setProfile(await profileRes.json());
        setScanStatus(await scanRes.json());
        setHistory(await histRes.json());
        setCategories(await catRes.json());
      }
    } catch (err) {
      setError("Failed to load status");
      toast({ title: "Error", description: "Failed to load status. Please try again.", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch("/api/extension/devices");
      if (res.ok) {
        const data = await res.json();
        setDevices(data.devices ?? []);
      }
    } catch { /* not authenticated yet */ }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  // Poll for scan progress
  useEffect(() => {
    if (!scanStatus?.running) return;
    const interval = setInterval(() => {
      fetch("/api/scan/status")
        .then((r) => r.json())
        .then((data: ScanStatus) => {
          setScanStatus(data);
          if (!data.running) {
            fetch("/api/scan/history").then((r) => r.json()).then(setHistory);
            fetch("/api/scan/categories").then((r) => r.json()).then(setCategories);
          }
        });
    }, 3000);
    return () => clearInterval(interval);
  }, [scanStatus?.running]);

  // Pairing countdown
  useEffect(() => {
    if (!pairingCode) return;
    const target = new Date(pairingCode.expiresAt).getTime();
    const tick = () => {
      const remaining = Math.max(0, Math.round((target - Date.now()) / 1000));
      setPairingCountdown(remaining);
      if (remaining === 0) {
        setPairingCode(null);
        setPairingModalOpen(false);
      }
    };
    tick();
    countdownRef.current = setInterval(tick, 1000);
    return () => { if (countdownRef.current) clearInterval(countdownRef.current); };
  }, [pairingCode]);

  const handleConnectGmail = async () => {
    setConnecting(true); setError(null);
    try {
      const res = await fetch("/api/gmail/oauth/start");
      const data = await res.json();
      if (data.auth_url) window.location.href = data.auth_url;
    } catch {
      setError("Failed to start OAuth flow");
      toast({ title: "Error", description: "Failed to start OAuth flow.", variant: "destructive" });
    } finally { setConnecting(false); }
  };

  const handleDisconnect = async () => {
    await fetch("/api/gmail/disconnect", { method: "POST" });
    setGmailStatus(null); setProfile(null); setScanStatus(null); setHistory(null); setCategories(null);
    await fetchStatus();
    toast({ title: "Disconnected", description: "Gmail account disconnected successfully." });
  };

  const handleStartScan = async (dryRun = false) => {
    setScanning(true); setError(null);
    try {
      const url = `/api/scan/start?dry_run=${dryRun}`;
      const res = await fetch(url, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Failed to start scan");
        toast({ title: "Error", description: data.detail || "Failed to start scan", variant: "destructive" });
      }
      await fetchStatus();
    } catch {
      setError("Failed to start scan");
      toast({ title: "Error", description: "Failed to start scan. Please try again.", variant: "destructive" });
    } finally { setScanning(false); }
  };

  const handleCreatePairingCode = async () => {
    const response = await fetch("/api/extension/pairing-codes", { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      toast({ title: "Pairing failed", description: data.detail || "Could not create pairing code", variant: "destructive" });
      return;
    }
    setPairingCode({ code: data.pairing_code, expiresAt: data.expires_at });
    setPairingModalOpen(true);
    fetchDevices();
  };

  const handleRevokeDevice = async (deviceId: string) => {
    const res = await fetch(`/api/extension/devices/${deviceId}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      toast({ title: "Device revoked", description: "Device session has been revoked." });
      fetchDevices();
    } else {
      toast({ title: "Error", description: "Could not revoke device.", variant: "destructive" });
    }
  };

  // OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth_success")) {
      setError(null);
      window.history.replaceState({}, "", "/");
      fetchStatus().then(fetchDevices);
    } else if (params.get("oauth_error")) {
      setError(`OAuth error: ${params.get("oauth_error")}`);
      window.history.replaceState({}, "", "/");
    }
  }, [fetchStatus, fetchDevices]);

  // Fetch devices when connected
  useEffect(() => {
    if (gmailStatus?.connected) fetchDevices();
  }, [gmailStatus?.connected, fetchDevices]);

  // ─── Loading ───
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl gradient-primary shadow-lg">
            <Mail className="h-7 w-7 text-white" />
            <span className="absolute inset-0 rounded-2xl animate-ping gradient-primary opacity-30" />
          </div>
          <p className="text-sm font-medium text-muted-foreground animate-pulse">Loading Gmail Cleaner…</p>
        </div>
      </div>
    );
  }

  // ─── Not connected ───
  if (!gmailStatus?.connected) {
    return (
      <OnboardingScreen
        oauthConfigured={gmailStatus?.oauth_configured ?? false}
        connecting={connecting}
        onConnect={handleConnectGmail}
        error={error}
        dark={dark}
        onToggleDark={() => setDark((d) => !d)}
      />
    );
  }

  const lastRun = scanStatus?.last_run;
  const isRunning = scanStatus?.running ?? false;

  return (
    <div className="min-h-screen bg-background">
      {/* Pairing code modal */}
      {pairingModalOpen && pairingCode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <Card className="w-full max-w-md mx-4 shadow-2xl border-primary/30 glow-primary">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <KeyRound className="h-5 w-5 text-primary" />
                  Extension Pairing Code
                </CardTitle>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPairingModalOpen(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Open the extension → Options → paste this one-time code to pair your device with this backend.
              </p>
              <div className="flex items-center justify-center rounded-xl bg-muted/60 border border-border/60 py-6">
                <span className="font-mono text-4xl font-bold tracking-[0.25em] text-foreground select-all">
                  {pairingCode.code}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <Clock className="h-3 w-3" />
                  Expires in {Math.floor(pairingCountdown / 60)}:{String(pairingCountdown % 60).padStart(2, "0")}
                </span>
                <span>Single-use · Not stored in plain text</span>
              </div>
              <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-1000"
                  style={{ width: `${(pairingCountdown / 600) * 100}%` }}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 py-3.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl gradient-primary shadow-md">
                <Mail className="h-4.5 w-4.5 text-white" style={{ width: 18, height: 18 }} />
              </div>
              <div>
                <h1 className="text-base font-bold text-foreground leading-tight">Gmail Cleaner</h1>
                <p className="text-xs text-muted-foreground leading-tight">{profile?.email || gmailStatus.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleCreatePairingCode} className="text-xs gap-1.5 h-8">
                <KeyRound className="h-3.5 w-3.5" /> Pair Extension
              </Button>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => fetchStatus()}>
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setDark((d) => !d)}>
                {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleDisconnect} className="text-xs h-8 text-muted-foreground">
                <Unlink className="mr-1.5 h-3.5 w-3.5" /> Disconnect
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="mx-auto max-w-7xl px-4 py-6">
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3.5 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Stat cards */}
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            accent="accent-primary"
            icon={<Inbox className="h-5 w-5" />}
            label="Total Emails"
            value={profile?.messages_total?.toLocaleString() ?? "—"}
            iconColor="text-primary"
            glowClass="glow-primary"
          />
          <StatCard
            accent="accent-danger"
            icon={<Trash2 className="h-5 w-5" />}
            label="Trashed"
            value={lastRun?.total_trashed ?? 0}
            iconColor="text-destructive"
            glowClass="glow-danger"
          />
          <StatCard
            accent="accent-success"
            icon={<Tag className="h-5 w-5" />}
            label="Sorted"
            value={lastRun?.total_labeled ?? 0}
            iconColor="text-green-500"
            glowClass="glow-success"
          />
          <StatCard
            accent="accent-amber"
            icon={<Sparkles className="h-5 w-5" />}
            label="Last Scan"
            value={lastRun?.completed_at ? new Date(lastRun.completed_at).toLocaleDateString() : "Never"}
            iconColor="text-amber-500"
            glowClass="glow-amber"
          />
        </div>

        {/* Scan control card */}
        <Card className="mb-6 overflow-hidden border-border/60 shadow-sm">
          <div className="h-1 gradient-primary" />
          <CardHeader className="pb-3 pt-4">
            <CardTitle className="flex items-center gap-2 text-base font-bold">
              <Play className="h-4 w-4 text-primary" />
              Email Scan
              {lastRun?.dry_run && (
                <Badge variant="outline" className="text-xs border-primary/30 text-primary bg-primary/5">
                  Dry Run Preview
                </Badge>
              )}
              {isRunning && (
                <Badge variant="secondary" className="ml-auto text-xs bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400">
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  Running
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isRunning ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Cpu className="h-4 w-4 text-amber-500 animate-pulse" />
                  AI is classifying emails… {lastRun?.total_scanned ?? 0}
                  {(lastRun?.total_emails ?? 0) > 0 && ` / ${lastRun!.total_emails}`} processed
                  {lastRun?.dry_run && <span className="text-primary-600 dark:text-primary-400 font-semibold">(Dry Run)</span>}
                </div>
                {(lastRun?.total_emails ?? 0) > 0 ? (
                  <div className="space-y-1">
                    <Progress
                      value={Math.round(((lastRun?.total_scanned ?? 0) / lastRun!.total_emails) * 100)}
                      className="h-2 bg-muted"
                    />
                    <p className="text-xs text-right text-muted-foreground tabular-nums">
                      {Math.round(((lastRun?.total_scanned ?? 0) / lastRun!.total_emails) * 100)}%
                    </p>
                  </div>
                ) : (
                  <Progress value={undefined} className="h-2 bg-muted" />
                )}
                <p className="text-xs text-muted-foreground">
                  {lastRun?.dry_run
                    ? "Classifying emails in preview mode. No messages will be moved or labeled."
                    : "Sorting into categories and removing junk. This may take a few minutes."}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm text-muted-foreground">
                  {lastRun ? (
                    <span>
                      Last scan: <strong>{lastRun.total_scanned}</strong> emails ·{" "}
                      <strong className="text-destructive">{lastRun.total_trashed}</strong> trashed ·{" "}
                      <strong className="text-green-600 dark:text-green-400">{lastRun.total_labeled}</strong> sorted
                      {lastRun.dry_run && <span className="ml-1.5 text-primary-600 dark:text-primary-400 font-semibold">(Preview)</span>}
                    </span>
                  ) : (
                    <span>No scans yet — run a preview or start a full scan to organize.</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => handleStartScan(true)}
                    disabled={scanning}
                    variant="outline"
                    className="border-primary/30 text-primary hover:bg-primary/5 transition-colors shadow-sm shrink-0"
                  >
                    {scanning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                    {scanning ? "Starting…" : "Preview Scan (Dry Run)"}
                  </Button>
                  <Button
                    onClick={() => handleStartScan(false)}
                    disabled={scanning}
                    className="gradient-primary text-white hover:opacity-90 transition-opacity shadow-md shrink-0"
                  >
                    {scanning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                    {scanning ? "Starting…" : "Start Full Scan"}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs defaultValue="charts" className="w-full">
          <TabsList className="mb-4 bg-muted/60 border border-border/50">
            <TabsTrigger value="charts" className="gap-1.5">
              <BarChart3 className="h-3.5 w-3.5" /> Breakdown
            </TabsTrigger>
            <TabsTrigger value="queue" className="gap-1.5">
              <Tag className="h-3.5 w-3.5" /> Review Queue
            </TabsTrigger>
            <TabsTrigger value="history" className="gap-1.5">
              <History className="h-3.5 w-3.5" /> History
            </TabsTrigger>
            <TabsTrigger value="devices" className="gap-1.5">
              <Monitor className="h-3.5 w-3.5" /> Devices
              {devices.filter((d) => !d.revoked).length > 0 && (
                <Badge className="ml-1 h-4 w-4 p-0 text-[10px] flex items-center justify-center">
                  {devices.filter((d) => !d.revoked).length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="charts">
            <ChartsTab categories={categories} />
          </TabsContent>

          <TabsContent value="queue">
            <ReviewQueueTab classifications={scanStatus?.classifications ?? []} />
          </TabsContent>

          <TabsContent value="history">
            <HistoryTab history={history} />
          </TabsContent>

          <TabsContent value="devices">
            <DevicesTab
              devices={devices}
              onRevoke={handleRevokeDevice}
              onCreateCode={handleCreatePairingCode}
              onRefresh={fetchDevices}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// ─── Onboarding ───────────────────────────────────────────────────────────────

function OnboardingScreen({
  oauthConfigured, connecting, onConnect, error, dark, onToggleDark,
}: {
  oauthConfigured: boolean;
  connecting: boolean;
  onConnect: () => void;
  error: string | null;
  dark: boolean;
  onToggleDark: () => void;
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4">
      <Button variant="outline" size="icon" className="fixed top-4 right-4 h-8 w-8" onClick={onToggleDark}>
        {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>

      <div className="w-full max-w-md">
        {/* Brand mark */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl gradient-primary shadow-xl">
            <Mail className="h-9 w-9 text-white" />
            <div className="absolute -inset-1 rounded-3xl gradient-primary opacity-30 blur-md" />
          </div>
          <div className="text-center">
            <h1 className="text-3xl font-bold text-foreground">Gmail Cleaner</h1>
            <p className="mt-1 text-sm text-muted-foreground">AI-powered inbox sorting & cleanup</p>
          </div>
        </div>

        <Card className="border-border/60 shadow-lg">
          <CardContent className="pt-6 space-y-5">
            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {!oauthConfigured ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 space-y-3">
                <h3 className="font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Google OAuth Setup Required
                </h3>
                <ol className="text-sm text-muted-foreground list-decimal list-inside space-y-1.5">
                  <li>Go to Google Cloud Console → APIs &amp; Services → Credentials</li>
                  <li>Create an OAuth 2.0 Client ID (Web application)</li>
                  <li>Add the redirect URI below to Authorized redirect URIs</li>
                  <li>Enable the Gmail API for your project</li>
                  <li>Add <code className="text-xs rounded bg-muted px-1">GOOGLE_OAUTH_CLIENT_ID</code> and <code className="text-xs rounded bg-muted px-1">GOOGLE_OAUTH_CLIENT_SECRET</code> to .env</li>
                </ol>
                <Separator />
                <p className="text-xs text-muted-foreground">
                  Redirect URI:{" "}
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {window.location.origin}/api/gmail/oauth/callback
                  </code>
                </p>
              </div>
            ) : (
              <Button
                onClick={onConnect}
                disabled={connecting}
                className="w-full gradient-primary text-white hover:opacity-90 transition-opacity shadow-md"
                size="lg"
              >
                {connecting ? (
                  <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Connecting…</>
                ) : (
                  <><Mail className="mr-2 h-5 w-5" /> Connect Gmail Account</>
                )}
              </Button>
            )}

            <div className="grid grid-cols-3 gap-2">
              <FeatureBadge icon="🗑️" label="Trash junk" />
              <FeatureBadge icon="🏷️" label="Sort categories" />
              <FeatureBadge icon="✨" label="AI-powered" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FeatureBadge({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-muted/40 p-3">
      <span className="text-xl leading-none">{icon}</span>
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
    </div>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({
  accent, icon, label, value, iconColor, glowClass,
}: {
  accent: string;
  icon: React.ReactNode;
  label: string;
  value: string | number;
  iconColor: string;
  glowClass: string;
}) {
  return (
    <div className={`stat-card ${accent} group hover:${glowClass}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
          <p className="mt-1.5 text-2xl font-bold text-foreground tabular-nums">{value}</p>
        </div>
        <div className={`rounded-xl p-2 bg-muted/60 ${iconColor} transition-transform group-hover:scale-110 duration-200`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

// ─── Charts tab ───────────────────────────────────────────────────────────────

function ChartsTab({ categories }: { categories: CategoryBreakdown | null }) {
  if (!categories || (categories.categories.length === 0 && categories.crap_count === 0)) {
    return (
      <Card className="border-border/60">
        <CardContent className="py-16 text-center text-muted-foreground">
          <BarChart3 className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No scan data yet</p>
          <p className="text-xs mt-1">Run a scan to see your email breakdown by category.</p>
        </CardContent>
      </Card>
    );
  }

  const allCats = [
    ...categories.categories.map((c) => ({ ...c, isCrap: false })),
    ...(categories.crap_count > 0 ? [{ category: "crap", count: categories.crap_count, isCrap: true }] : []),
  ];
  const total = allCats.reduce((sum, c) => sum + c.count, 0);
  const maxCount = Math.max(...allCats.map((c) => c.count), 1);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Category Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {allCats.map((cat) => {
            const isCrap = cat.isCrap;
            const label = isCrap ? "Trashed (Junk)" : CATEGORY_LABELS[cat.category] || cat.category;
            const icon = isCrap ? "🗑️" : CATEGORY_ICONS[cat.category] || "📧";
            const colors = isCrap
              ? { bg: "hsl(0 84% 95%)", text: "hsl(0 84% 40%)", bar: "hsl(0 84% 60%)" }
              : CATEGORY_COLORS[cat.category] || { bg: "hsl(220 50% 94%)", text: "hsl(220 50% 40%)", bar: "hsl(220 50% 55%)" };
            const pct = (cat.count / maxCount) * 100;
            const share = total > 0 ? Math.round((cat.count / total) * 100) : 0;

            return (
              <div key={cat.category} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 font-medium">
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{ background: colors.bg, color: colors.text }}
                    >
                      {icon} {label}
                    </span>
                  </span>
                  <span className="font-semibold text-foreground tabular-nums">
                    {cat.count}
                    <span className="ml-1 text-xs text-muted-foreground font-normal">({share}%)</span>
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700 ease-out"
                    style={{ width: `${pct}%`, background: colors.bar }}
                  />
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/50">
              <span className="text-sm font-medium text-muted-foreground">Total classified</span>
              <span className="text-xl font-bold text-foreground tabular-nums">{total.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-destructive/10 border border-destructive/20">
              <span className="text-sm font-medium text-destructive/80">🗑️ Junk trashed</span>
              <span className="text-xl font-bold text-destructive tabular-nums">{categories.crap_count.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-green-500/10 border border-green-500/20">
              <span className="text-sm font-medium text-green-700 dark:text-green-400">🏷️ Categories assigned</span>
              <span className="text-xl font-bold text-green-600 dark:text-green-400 tabular-nums">
                {categories.categories.reduce((s, c) => s + c.count, 0).toLocaleString()}
              </span>
            </div>
          </div>
          <Separator />
          <p className="text-xs text-muted-foreground">
            Classification by Gemini AI. Crap = promotional junk, spam, and low-value automated email.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Review queue ─────────────────────────────────────────────────────────────

function ReviewQueueTab({ classifications }: { classifications: EmailClassification[] }) {
  if (classifications.length === 0) {
    return (
      <Card className="border-border/60">
        <CardContent className="py-16 text-center text-muted-foreground">
          <Tag className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No classifications yet</p>
          <p className="text-xs mt-1">Run a scan to see processed emails here.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          Recent Classifications
          <Badge variant="secondary" className="ml-auto">{classifications.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[520px] pr-3">
          <div className="space-y-2">
            {classifications.map((cls) => (
              <ClassificationRow key={cls.message_id} cls={cls} />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function ClassificationRow({ cls }: { cls: EmailClassification }) {
  const colors = cls.is_crap
    ? { bg: "hsl(0 84% 95%)", text: "hsl(0 84% 40%)", bar: "hsl(0 84% 60%)" }
    : cls.category
      ? CATEGORY_COLORS[cls.category] || { bg: "hsl(220 50% 94%)", text: "hsl(220 50% 40%)", bar: "hsl(220 50% 55%)" }
      : null;

  const actionIcon = cls.action_taken === "trashed"
    ? <Trash2 className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
    : cls.action_taken === "labeled"
      ? <Tag className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
      : cls.action_taken?.includes("failed")
        ? <XCircle className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
        : <Inbox className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />;

  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/50 p-3 hover:bg-muted/40 transition-colors duration-150">
      <div className="mt-0.5">{actionIcon}</div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-foreground truncate">{cls.subject || "(no subject)"}</p>
        <p className="text-xs text-muted-foreground truncate mt-0.5">{cls.sender}</p>
        <div className="mt-1.5 flex items-center gap-2 flex-wrap">
          {cls.is_crap ? (
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: "hsl(0 84% 95%)", color: "hsl(0 84% 40%)" }}>
              🗑️ Junk
            </span>
          ) : cls.category && colors ? (
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: colors.bg, color: colors.text }}>
              {CATEGORY_ICONS[cls.category] || "📧"} {CATEGORY_LABELS[cls.category] || cls.category}
            </span>
          ) : null}
          {cls.crap_reason && (
            <span className="text-xs text-muted-foreground">{cls.crap_reason}</span>
          )}
          {cls.confidence > 0 && (
            <span className="text-xs text-muted-foreground ml-auto">{Math.round(cls.confidence * 100)}%</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── History tab ──────────────────────────────────────────────────────────────

function HistoryTab({ history }: { history: ScanHistory | null }) {
  if (!history || history.history.length === 0) {
    return (
      <Card className="border-border/60">
        <CardContent className="py-16 text-center text-muted-foreground">
          <History className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No scan history yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Scan History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {history.history.map((run) => (
            <HistoryRow key={run.id} run={run} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function HistoryRow({ run }: { run: import("./types").ScanRun }) {
  const isCompleted = run.status === "completed";
  const isFailed = run.status === "failed";

  const statusIcon = isCompleted
    ? <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
    : isFailed
      ? <XCircle className="h-4 w-4 text-destructive flex-shrink-0" />
      : <Loader2 className="h-4 w-4 animate-spin text-primary flex-shrink-0" />;

  const dateStr = run.started_at ? new Date(run.started_at).toLocaleString() : "—";

  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/50 p-3.5">
      <div className="mt-0.5">{statusIcon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-foreground">{dateStr}</span>
          <Badge
            variant={isCompleted ? "default" : isFailed ? "destructive" : "secondary"}
            className="text-xs"
          >
            {run.status}
          </Badge>
          {run.dry_run && (
            <Badge variant="outline" className="text-xs border-primary/30 text-primary bg-primary/5">
              preview
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
          <span>{run.total_scanned} scanned</span>
          <span className="text-destructive font-medium">{run.total_trashed} trashed</span>
          <span className="text-green-600 dark:text-green-400 font-medium">{run.total_labeled} sorted</span>
        </div>
        {run.error_message && (
          <p className="text-xs text-destructive mt-1">{run.error_message}</p>
        )}
      </div>
    </div>
  );
}

// ─── Devices tab ──────────────────────────────────────────────────────────────

function DevicesTab({
  devices, onRevoke, onCreateCode, onRefresh,
}: {
  devices: DeviceSession[];
  onRevoke: (id: string) => void;
  onCreateCode: () => void;
  onRefresh: () => void;
}) {
  const activeDevices = devices.filter((d) => !d.revoked);
  const revokedDevices = devices.filter((d) => d.revoked);

  return (
    <div className="space-y-4">
      <Card className="border-border/60 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4 text-primary" />
              Paired Extension Devices
              {activeDevices.length > 0 && (
                <Badge className="gradient-primary text-white border-0">{activeDevices.length}</Badge>
              )}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={onRefresh} className="h-7 text-xs gap-1">
                <RefreshCw className="h-3 w-3" /> Refresh
              </Button>
              <Button size="sm" onClick={onCreateCode} className="h-7 text-xs gradient-primary text-white border-0 shadow gap-1.5">
                <KeyRound className="h-3 w-3" /> New Pairing Code
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {activeDevices.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">
              <Monitor className="mx-auto mb-3 h-10 w-10 opacity-30" />
              <p className="text-sm font-medium">No paired devices</p>
              <p className="text-xs mt-1 max-w-xs mx-auto">
                Generate a pairing code and enter it in the extension Options page to link a device.
              </p>
              <Button variant="outline" size="sm" className="mt-4 gap-1.5" onClick={onCreateCode}>
                <KeyRound className="h-3.5 w-3.5" /> Generate Pairing Code
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {activeDevices.map((device) => (
                <DeviceRow key={device.id} device={device} onRevoke={onRevoke} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {revokedDevices.length > 0 && (
        <Card className="border-border/60 shadow-sm opacity-70">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-muted-foreground">
              <ShieldOff className="h-4 w-4" />
              Revoked Devices
              <Badge variant="secondary" className="text-xs">{revokedDevices.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {revokedDevices.map((device) => (
                <DeviceRow key={device.id} device={device} onRevoke={onRevoke} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DeviceRow({ device, onRevoke }: { device: DeviceSession; onRevoke: (id: string) => void }) {
  const lastSeen = device.last_seen_at ? new Date(device.last_seen_at) : null;
  const created = device.created_at ? new Date(device.created_at) : null;
  const minutesAgo = lastSeen ? Math.round((Date.now() - lastSeen.getTime()) / 60000) : null;

  const freshLabel = minutesAgo !== null
    ? minutesAgo < 2 ? "Just now" : minutesAgo < 60 ? `${minutesAgo}m ago` : `${Math.round(minutesAgo / 60)}h ago`
    : null;

  return (
    <div className={`flex items-center gap-3 rounded-xl border p-3.5 transition-colors ${device.revoked ? "border-border/30 bg-muted/20" : "border-border/60 hover:bg-muted/30"}`}>
      <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${device.revoked ? "bg-muted" : "bg-primary/10"}`}>
        <Monitor className={`h-4 w-4 ${device.revoked ? "text-muted-foreground" : "text-primary"}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`font-medium text-sm truncate ${device.revoked ? "text-muted-foreground" : "text-foreground"}`}>
            {device.device_name}
          </p>
          {device.revoked ? (
            <Badge variant="outline" className="text-xs text-muted-foreground shrink-0">Revoked</Badge>
          ) : (
            <Badge className="text-xs bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/20 shrink-0">Active</Badge>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
          {device.extension_version && <span>v{device.extension_version}</span>}
          {created && <span>Paired {created.toLocaleDateString()}</span>}
          {freshLabel && <span>· Seen {freshLabel}</span>}
        </div>
      </div>
      {!device.revoked && (
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive shrink-0"
          onClick={() => onRevoke(device.id)}
        >
          <ShieldOff className="mr-1 h-3 w-3" /> Revoke
        </Button>
      )}
    </div>
  );
}

export default App;
