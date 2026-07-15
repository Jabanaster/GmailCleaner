import type {
  GmailStatus,
  GmailProfile,
  ScanStatus,
  ScanHistory,
  CategoryBreakdown,
  DeviceSession,
} from "./types";
import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Mail,
  Trash2,
  Tag,
  Play,
  RefreshCw,
  Unlink,
  Loader2,
  Inbox,
  AlertTriangle,
  History,
  BarChart3,
  Sparkles,
  KeyRound,
  Monitor,
  Moon,
  Sun,
  Clock,
  Cpu,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { StatCard } from "@/components/StatCard";
import { OnboardingScreen } from "@/components/OnboardingScreen";
import { ChartsTab } from "@/components/ChartsTab";
import { ReviewQueueTab } from "@/components/ReviewQueueTab";
import { HistoryTab } from "@/components/HistoryTab";
import { DevicesTab } from "@/components/DevicesTab";

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

// ─── App ─────────────────────────────────────────────────────────────────────

function AppContent() {
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
      const status = await api.getGmailStatus();
      setGmailStatus(status);
      setError(null);

      if (status.connected) {
        const [profileData, scanData, histData, catData] = await Promise.all([
          api.getGmailProfile().catch(() => null),
          api.getScanStatus(),
          api.getScanHistory(),
          api.getScanCategories(),
        ]);

        if (profileData) setProfile(profileData);
        setScanStatus(scanData);
        setHistory(histData);
        setCategories(catData);
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
      const activeDevices = await api.getDevices();
      setDevices(activeDevices);
    } catch { /* not authenticated yet */ }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  // Poll for scan progress
  useEffect(() => {
    if (!scanStatus?.running) return;
    const interval = setInterval(() => {
      api.getScanStatus()
        .then((data: ScanStatus) => {
          setScanStatus(data);
          if (!data.running) {
            api.getScanHistory().then(setHistory);
            api.getScanCategories().then(setCategories);
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
      const data = await api.startOAuth();
      if (data.auth_url) window.location.href = data.auth_url;
    } catch {
      setError("Failed to start OAuth flow");
      toast({ title: "Error", description: "Failed to start OAuth flow.", variant: "destructive" });
    } finally { setConnecting(false); }
  };

  const handleDisconnect = async () => {
    await api.disconnectGmail();
    setGmailStatus(null); setProfile(null); setScanStatus(null); setHistory(null); setCategories(null);
    await fetchStatus();
    toast({ title: "Disconnected", description: "Gmail account disconnected successfully." });
  };

  const handleStartScan = async (dryRun = false) => {
    setScanning(true); setError(null);
    try {
      await api.startScan(dryRun);
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || "Failed to start scan");
      toast({ title: "Error", description: err.message || "Failed to start scan", variant: "destructive" });
    } finally { setScanning(false); }
  };

  const handleCreatePairingCode = async () => {
    try {
      const data = await api.createPairingCode();
      setPairingCode({ code: data.pairing_code, expiresAt: data.expires_at });
      setPairingModalOpen(true);
      fetchDevices();
    } catch (err: any) {
      toast({ title: "Pairing failed", description: err.message || "Could not create pairing code", variant: "destructive" });
    }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    try {
      await api.revokeDevice(deviceId);
      toast({ title: "Device revoked", description: "Device session has been revoked." });
      fetchDevices();
    } catch {
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
      const oauthError = params.get("oauth_error") ?? "unknown";
      const message =
        oauthError === "invalid_state"
          ? "Sign-in session expired or was interrupted. Click Connect Gmail again."
          : `OAuth error: ${oauthError}`;
      setError(message);
      toast({ title: "Gmail sign-in failed", description: message, variant: "destructive" });
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

function App() {
  return (
    <ErrorBoundary>
      <AppContent />
    </ErrorBoundary>
  );
}

export default App;
