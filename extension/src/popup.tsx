import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { sendRuntimeMessage } from "./lib/messaging";
import type { BackendAuthStatus, GoogleProfile, ScanJobStatus } from "./lib/types";
import "./styles.css";

const CATEGORY_ICONS: Record<string, string> = {
  work: "💼", finance: "💰", personal: "👤", travel: "✈️",
  receipts: "🧾", social: "🌐", newsletters: "📰", promotions: "🏷️",
  "trash-review": "🗑️", uncategorized: "❓",
};

function Popup() {
  const [profile, setProfile] = useState<GoogleProfile | null>(null);
  const [scan, setScan] = useState<ScanJobStatus | null>(null);
  const [backendAuth, setBackendAuth] = useState<BackendAuthStatus>({ state: "unpaired" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void sendRuntimeMessage<GoogleProfile>({ type: "auth:getProfile" }).then(setProfile).catch(() => undefined);
    void sendRuntimeMessage<ScanJobStatus | null>({ type: "scan:getLatest" }).then(setScan).catch(() => undefined);
    void sendRuntimeMessage<BackendAuthStatus>({ type: "backend:authStatus" })
      .then(setBackendAuth)
      .catch(() => setBackendAuth({ state: "unavailable" }));
  }, []);

  async function connect() {
    setBusy(true); setError("");
    try { setProfile(await sendRuntimeMessage({ type: "auth:getProfile", interactive: true })); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not connect to Google"); }
    finally { setBusy(false); }
  }

  async function startScan() {
    setBusy(true); setError("");
    try { setScan(await sendRuntimeMessage<ScanJobStatus>({ type: "scan:previewInbox" })); }
    catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
      setScan(await sendRuntimeMessage<ScanJobStatus | null>({ type: "scan:getLatest" }).catch(() => null));
    }
    finally { setBusy(false); }
  }

  const ready = Boolean(profile) && backendAuth.state === "paired";

  const stateInfo = {
    unpaired:    { label: "Backend unpaired",   dotClass: "" },
    paired:      { label: "Fully connected",     dotClass: "ok" },
    expired:     { label: "Session expired",     dotClass: "bad" },
    unavailable: { label: "Backend unavailable", dotClass: "bad" },
  }[backendAuth.state] ?? { label: backendAuth.state, dotClass: "" };

  return (
    <main className="app popup">
      {/* Brand header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 9,
          background: "linear-gradient(135deg, #6366f1, #7c3aed)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 8px rgba(99,102,241,0.4)",
          fontSize: 16, flexShrink: 0,
        }}>✉️</div>
        <div>
          <p className="eyebrow" style={{ marginBottom: 0 }}>Extension</p>
          <h1 style={{ fontSize: 16 }}>Gmail Cleaner</h1>
        </div>
      </div>

      {/* Google account card */}
      <section className="card">
        <div className="row">
          <span className="status">
            <i className={`dot ${profile ? "ok" : ""}`} />
            {profile ? (
              <span style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {profile.email}
              </span>
            ) : "Gmail not connected"}
          </span>
          {!profile && (
            <button className="button secondary" disabled={busy} onClick={connect} style={{ fontSize: 12, padding: "6px 12px" }}>
              {busy ? "Connecting…" : "Connect"}
            </button>
          )}
        </div>
      </section>

      {/* Backend status card */}
      <section className="card stack">
        <div className="row">
          <span className="status">
            <i className={`dot ${stateInfo.dotClass}`} />
            {stateInfo.label}
          </span>
        </div>

        {profile && backendAuth.state === "unpaired" && (
          <>
            <div className="row" style={{ gap: 8 }}>
              <button className="button secondary" style={{ flex: 1, fontSize: 12, padding: "7px 10px" }}
                onClick={() => void sendRuntimeMessage({ type: "backend:openDashboard" })}>
                Open dashboard
              </button>
              <button className="button secondary" style={{ flex: 1, fontSize: 12, padding: "7px 10px" }}
                onClick={() => chrome.runtime.openOptionsPage()}>
                Pair backend
              </button>
            </div>
            <p className="muted">Generate a code from your signed-in dashboard, then enter it in Settings.</p>
          </>
        )}

        {backendAuth.state === "paired" && backendAuth.session && (
          <div style={{ background: "var(--brand-soft)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: "var(--brand-text)", marginBottom: 2 }}>
              {backendAuth.session.deviceName}
            </p>
            <p className="muted">{backendAuth.session.environment} · {backendAuth.session.user.displayName}</p>
          </div>
        )}

        {backendAuth.state === "paired" && (
          <button className="button danger" style={{ fontSize: 12, padding: "7px 12px" }}
            onClick={async () => { await sendRuntimeMessage({ type: "backend:disconnect" }); setBackendAuth({ state: "unpaired" }); }}>
            Disconnect backend
          </button>
        )}

        {(backendAuth.state === "expired" || backendAuth.state === "unavailable") && (
          <>
            {backendAuth.error && <div className="error">{backendAuth.error}</div>}
            <button className="button secondary" style={{ fontSize: 12, padding: "7px 12px" }}
              onClick={() => void sendRuntimeMessage<BackendAuthStatus>({ type: "backend:authStatus" }).then(setBackendAuth)}>
              Retry connection
            </button>
          </>
        )}
      </section>

      {/* Scan card */}
      <section className="card stack">
        <div>
          <h2 style={{ marginBottom: 4 }}>Preview scan</h2>
          <p className="muted">Reads recent metadata and sends to your backend for AI classification. Nothing is changed in Gmail.</p>
        </div>

        {scan && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <i className={`dot ${busy ? "busy" : scan.state === "completed" ? "ok" : scan.state === "failed" ? "bad" : ""}`} />
            <span className="muted">{busy ? "Scanning…" : `${scan.state} · ${scan.processed}/${scan.total} · ${scan.proposals.length} proposals`}</span>
          </div>
        )}

        <button className="button" disabled={busy || !ready} onClick={startScan}>
          {busy ? "Working…" : "Preview inbox scan"}
        </button>

        {!ready && !busy && (
          <p className="muted" style={{ fontSize: 11 }}>
            {!profile ? "Connect Google account first." : "Pair with the backend first."}
          </p>
        )}

        {error && <div className="error">{error}</div>}
      </section>

      {/* Open side panel */}
      <button
        className="button ghost"
        style={{ width: "100%", marginTop: 10, fontSize: 12 }}
        onClick={() => void sendRuntimeMessage({ type: "sidepanel:open" }).catch((e) => setError(e.message))}
      >
        📋 Open full review panel
      </button>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><Popup /></React.StrictMode>);
