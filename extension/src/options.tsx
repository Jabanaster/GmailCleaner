import React, { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { DEFAULT_SETTINGS, getSettings, saveSettings } from "./lib/chrome-storage";
import { isLocalDevelopmentUrl, normalizeBackendUrl } from "./lib/backend-url";
import { sendRuntimeMessage } from "./lib/messaging";
import type { BackendAuthStatus, ExtensionSettings } from "./lib/types";
import "./styles.css";

function Options() {
  const [settings, setSettings] = useState<ExtensionSettings>(DEFAULT_SETTINGS);
  const [pairingCode, setPairingCode] = useState("");
  const [deviceName, setDeviceName] = useState(`${navigator.platform || "Desktop"} Chrome`);
  const [auth, setAuth] = useState<BackendAuthStatus>({ state: "unpaired" });
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [pairing, setPairing] = useState(false);

  const refreshStatus = () =>
    sendRuntimeMessage<BackendAuthStatus>({ type: "backend:authStatus" })
      .then(setAuth)
      .catch(() => setAuth({ state: "unavailable" }));

  useEffect(() => {
    void getSettings().then(setSettings);
    void refreshStatus();
  }, []);

  let devMode = false;
  try { devMode = isLocalDevelopmentUrl(settings.backendBaseUrl); } catch { /* ignore */ }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setSaving(true);
    try {
      const clean = {
        ...settings,
        backendBaseUrl: normalizeBackendUrl(settings.backendBaseUrl),
        scanLimit: Math.min(Math.max(settings.scanLimit, 1), 50),
      };
      if (!isLocalDevelopmentUrl(clean.backendBaseUrl)) {
        const granted = await chrome.permissions.request({ origins: [`${clean.backendBaseUrl}/*`] });
        if (!granted) throw new Error("Chrome access to this backend origin was not granted");
      }
      await saveSettings(clean);
      setSettings(clean);
      setMessage("Settings saved.");
      await refreshStatus();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  async function pair() {
    setMessage("");
    setPairing(true);
    try {
      setAuth(await sendRuntimeMessage({ type: "backend:pair", pairingCode, deviceName }));
      setPairingCode("");
      setMessage("Backend paired successfully.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Pairing failed");
    } finally {
      setPairing(false);
    }
  }

  async function disconnect() {
    await sendRuntimeMessage({ type: "backend:disconnect" });
    setAuth({ state: "unpaired" });
    setMessage("Backend disconnected.");
  }

  async function testConnection() {
    setMessage("");
    try {
      await sendRuntimeMessage({ type: "backend:health" });
      setMessage("Backend is reachable ✓");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Backend unavailable");
    }
  }

  const isPaired = auth.state === "paired";
  const isError = message && (
    message.toLowerCase().includes("failed") ||
    message.toLowerCase().includes("invalid") ||
    message.toLowerCase().includes("unavailable") ||
    message.toLowerCase().includes("error") ||
    message.toLowerCase().includes("not granted")
  );

  return (
    <main className="app">
      {/* Brand header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12,
          background: "linear-gradient(135deg, #6366f1, #7c3aed)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 10px rgba(99,102,241,0.4)", fontSize: 20, flexShrink: 0,
        }}>✉️</div>
        <div>
          <p className="eyebrow" style={{ marginBottom: 0 }}>Google Email Organizer</p>
          <h1>Settings</h1>
        </div>
      </div>

      {/* Backend URL settings */}
      <form className="card stack" onSubmit={submit}>
        <h2 style={{ marginBottom: 6 }}>Connection</h2>

        <label>
          FastAPI backend URL
          <input
            type="url"
            required
            value={settings.backendBaseUrl}
            onChange={(e) => setSettings({ ...settings, backendBaseUrl: e.target.value })}
            placeholder="http://localhost:5273"
          />
        </label>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          fontSize: 11, fontWeight: 600,
          color: devMode ? "var(--amber-text)" : "var(--text-2)",
          background: devMode ? "var(--amber-soft)" : "var(--surface-2)",
          border: `1px solid ${devMode ? "rgba(245,158,11,0.25)" : "var(--border)"}`,
          borderRadius: 6, padding: "4px 8px",
        }}>
          {devMode ? "⚠️" : "🔒"} {devMode ? "Localhost development · HTTP allowed" : "Production · HTTPS required"}
        </div>

        <label>
          Messages per preview <span className="muted">(1–50)</span>
          <input
            type="number"
            min="1" max="50"
            value={settings.scanLimit}
            onChange={(e) => setSettings({ ...settings, scanLimit: Number(e.target.value) })}
          />
        </label>

        <label className="switch">
          <input
            type="checkbox"
            checked={settings.dryRunMode}
            onChange={(e) => setSettings({ ...settings, dryRunMode: e.target.checked })}
          />
          Dry-run mode (preview only — no Gmail changes)
        </label>

        <div className="row" style={{ marginTop: 4 }}>
          <button className="button" type="submit" disabled={saving} style={{ flex: 1 }}>
            {saving ? "Saving…" : "Save settings"}
          </button>
          <button className="button secondary" type="button" onClick={testConnection} style={{ flex: 1 }}>
            Test connection
          </button>
        </div>
      </form>

      {/* Pairing section */}
      <section className="card stack">
        <div className="row">
          <h2 style={{ marginBottom: 0 }}>Backend pairing</h2>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 999,
            background: isPaired ? "var(--green-soft)" : auth.state === "expired" ? "var(--red-soft)" : "var(--surface-2)",
            color: isPaired ? "var(--green-text)" : auth.state === "expired" ? "var(--red-text)" : "var(--text-2)",
            border: `1px solid ${isPaired ? "rgba(16,185,129,0.25)" : auth.state === "expired" ? "rgba(239,68,68,0.25)" : "var(--border)"}`,
          }}>
            {isPaired ? "✓ Paired" : auth.state === "expired" ? "Expired" : auth.state === "unavailable" ? "Unavailable" : "Unpaired"}
          </span>
        </div>

        {isPaired && auth.session && (
          <div style={{ background: "var(--brand-soft)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: "var(--brand-text)", marginBottom: 2 }}>
              {auth.session.deviceName}
            </p>
            <p className="muted">
              {auth.session.user.displayName} · {auth.session.environment} ·{" "}
              <span style={{ fontFamily: "monospace" }}>v{auth.session.deviceSessionId.slice(0, 8)}</span>
            </p>
          </div>
        )}

        {!isPaired ? (
          <>
            <label>
              One-time pairing code
              <input
                type="text"
                value={pairingCode}
                maxLength={9}
                placeholder="ABCD-EFGH"
                onChange={(e) => setPairingCode(e.target.value.toUpperCase())}
              />
            </label>
            <label>
              Device name
              <input
                type="text"
                value={deviceName}
                maxLength={100}
                onChange={(e) => setDeviceName(e.target.value)}
              />
            </label>
            <button className="button" type="button" onClick={pair} disabled={pairing || !pairingCode}>
              {pairing ? "Pairing…" : "Pair backend"}
            </button>
            <p className="muted" style={{ fontSize: 11 }}>
              Generate the one-time code from the authenticated web dashboard. It expires in 10 minutes.
            </p>
          </>
        ) : (
          <button className="button danger" type="button" onClick={disconnect}>
            Disconnect backend
          </button>
        )}

        {message && (
          <div className={isError ? "error" : "success"}>{message}</div>
        )}
      </section>

      {/* About */}
      <section className="card">
        <div className="row">
          <span className="muted">Gmail Cleaner · Extension</span>
          <span className="muted">{chrome.runtime.getManifest().version}</span>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><Options /></React.StrictMode>);
