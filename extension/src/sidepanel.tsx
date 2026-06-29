import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { sendRuntimeMessage } from "./lib/messaging";
import type { BackendAuthStatus, ClassificationProposal, GoogleProfile, ScanJobStatus } from "./lib/types";
import "./styles.css";

const CATEGORY_LABELS: Record<string, string> = {
  work: "Work", finance: "Finance", personal: "Personal", travel: "Travel",
  receipts: "Receipts", social: "Social", newsletters: "Newsletters",
  promotions: "Promotions", "trash-review": "Trash Review", uncategorized: "Uncategorized",
};

const CATEGORY_ICONS: Record<string, string> = {
  work: "💼", finance: "💰", personal: "👤", travel: "✈️",
  receipts: "🧾", social: "🌐", newsletters: "📰", promotions: "🏷️",
  "trash-review": "🗑️", uncategorized: "❓",
};

function categoryChipClass(label: string): string {
  const map: Record<string, string> = {
    work: "work", finance: "finance", personal: "personal", travel: "travel",
    receipts: "receipts", social: "social", newsletters: "newsletters",
    promotions: "promotions", "trash-review": "trash", uncategorized: "uncategorized",
  };
  return map[label] ?? "uncategorized";
}

function ProposalCard({ p }: { p: ClassificationProposal }) {
  const icon = CATEGORY_ICONS[p.proposedLabel] ?? "📧";
  const label = CATEGORY_LABELS[p.proposedLabel] ?? p.proposedLabel;
  const chipClass = categoryChipClass(p.proposedLabel);
  const confPct = Math.round(p.confidence * 100);

  return (
    <div className="proposal">
      <div className="row" style={{ marginBottom: 6, flexWrap: "wrap", gap: 6 }}>
        <span className={`chip ${chipClass}`}>{icon} {label}</span>
        <span className="confidence">{confPct}%</span>
      </div>
      {p.reason && <p className="muted" style={{ marginBottom: 4 }}>{p.reason}</p>}
      <p className="muted" style={{ fontSize: 11, fontFamily: "monospace", opacity: 0.7 }}>{p.messageId.slice(0, 16)}…</p>
      <div className="conf-bar">
        <div className="conf-bar-fill" style={{ width: `${confPct}%` }} />
      </div>
    </div>
  );
}

function SidePanel() {
  const [scan, setScan] = useState<ScanJobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [google, setGoogle] = useState<GoogleProfile | null>(null);
  const [auth, setAuth] = useState<BackendAuthStatus>({ state: "unpaired" });
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    void sendRuntimeMessage<ScanJobStatus | null>({ type: "scan:getLatest" }).then(setScan);
    void sendRuntimeMessage<GoogleProfile>({ type: "auth:getProfile" }).then(setGoogle).catch(() => undefined);
    void sendRuntimeMessage<BackendAuthStatus>({ type: "backend:authStatus" })
      .then(setAuth)
      .catch(() => setAuth({ state: "unavailable" }));
  }, []);

  async function scanInbox() {
    setBusy(true); setError("");
    try { setScan(await sendRuntimeMessage<ScanJobStatus>({ type: "scan:previewInbox" })); }
    catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
      setScan(await sendRuntimeMessage<ScanJobStatus | null>({ type: "scan:getLatest" }).catch(() => null));
    }
    finally { setBusy(false); }
  }

  const proposals = scan?.proposals ?? [];
  const allLabels = Array.from(new Set(proposals.map((p) => p.proposedLabel)));

  const filteredProposals = filter === "all" ? proposals : proposals.filter((p) => p.proposedLabel === filter);

  const trashCount = proposals.filter((p) => p.proposedLabel === "trash-review").length;
  const otherCount = proposals.length - trashCount;

  return (
    <main className="app" style={{ paddingBottom: 32 }}>
      {/* Brand header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10,
          background: "linear-gradient(135deg, #6366f1, #7c3aed)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 8px rgba(99,102,241,0.4)", fontSize: 18, flexShrink: 0,
        }}>✉️</div>
        <div>
          <p className="eyebrow" style={{ marginBottom: 0 }}>Gmail Cleaner</p>
          <h1 style={{ fontSize: 18 }}>Review desk</h1>
        </div>
      </div>
      <p className="muted" style={{ marginBottom: 0, fontSize: 11 }}>
        Read-only preview — no changes are made to Gmail until you approve them.
      </p>

      {/* Connection status */}
      <section className="card">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}>
            <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-3)", marginBottom: 2 }}>Gmail</p>
            <p style={{ fontSize: 12, fontWeight: 600, color: google ? "var(--green)" : "var(--red)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {google?.email ?? "Disconnected"}
            </p>
          </div>
          <div style={{ background: "var(--surface-2)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}>
            <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-3)", marginBottom: 2 }}>Organizer</p>
            <p style={{ fontSize: 12, fontWeight: 600, color: auth.state === "paired" ? "var(--green)" : auth.state === "unavailable" ? "var(--red)" : "var(--amber)" }}>
              {auth.state === "paired" ? auth.session?.deviceName ?? "Paired" : auth.state}
            </p>
          </div>
        </div>
        {auth.error && <div className="error" style={{ marginTop: 8 }}>{auth.error}</div>}
      </section>

      {/* Scan control */}
      <section className="card stack">
        <div className="row">
          <div>
            <h2 style={{ marginBottom: 2 }}>Inbox scan</h2>
            {scan && (
              <div className="status">
                <i className={`dot ${busy ? "busy" : scan.state === "completed" ? "ok" : scan.state === "failed" ? "bad" : ""}`} />
                {busy ? "Scanning…" : `${scan.state} · ${scan.processed}/${scan.total}`}
              </div>
            )}
          </div>
          <button
            className="button"
            disabled={busy || !google || auth.state !== "paired"}
            onClick={scanInbox}
            style={{ fontSize: 12, padding: "8px 14px", flexShrink: 0 }}
          >
            {busy ? "Scanning…" : "▶ Run preview"}
          </button>
        </div>
        {scan?.updatedAt && (
          <p className="muted" style={{ fontSize: 11 }}>
            Last updated {new Date(scan.updatedAt).toLocaleString()}
          </p>
        )}
        {error && <div className="error">{error}</div>}
      </section>

      {/* Proposals */}
      {proposals.length > 0 && (
        <section className="card stack">
          {/* Summary stats */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div style={{ background: "var(--red-soft)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius-sm)", padding: "8px 10px", textAlign: "center" }}>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--red-text)", lineHeight: 1 }}>{trashCount}</p>
              <p style={{ fontSize: 10, fontWeight: 600, color: "var(--red-text)", opacity: 0.8, marginTop: 2 }}>To trash</p>
            </div>
            <div style={{ background: "var(--brand-soft)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: "var(--radius-sm)", padding: "8px 10px", textAlign: "center" }}>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--brand-text)", lineHeight: 1 }}>{otherCount}</p>
              <p style={{ fontSize: 10, fontWeight: 600, color: "var(--brand-text)", opacity: 0.8, marginTop: 2 }}>To label</p>
            </div>
          </div>

          {/* Filter chips */}
          {allLabels.length > 1 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <button
                className={`button ${filter === "all" ? "" : "secondary"}`}
                style={{ fontSize: 11, padding: "4px 10px" }}
                onClick={() => setFilter("all")}
              >
                All ({proposals.length})
              </button>
              {allLabels.map((l) => (
                <button
                  key={l}
                  className={`button ${filter === l ? "" : "secondary"}`}
                  style={{ fontSize: 11, padding: "4px 10px" }}
                  onClick={() => setFilter(l)}
                >
                  {CATEGORY_ICONS[l] ?? "📧"} {CATEGORY_LABELS[l] ?? l} ({proposals.filter((p) => p.proposedLabel === l).length})
                </button>
              ))}
            </div>
          )}

          {/* Proposal list */}
          <div>
            {filteredProposals.map((p) => <ProposalCard key={p.messageId} p={p} />)}
          </div>
        </section>
      )}

      {proposals.length === 0 && !busy && (
        <section className="card" style={{ textAlign: "center", padding: "28px 14px" }}>
          <p style={{ fontSize: 32, marginBottom: 8 }}>📭</p>
          <p style={{ fontWeight: 600, marginBottom: 4 }}>No proposals yet</p>
          <p className="muted">Connect your accounts and run a preview scan to see AI classification results here.</p>
        </section>
      )}

      {/* Apply section — read-only notice */}
      <section className="card stack" style={{ opacity: 0.7 }}>
        <h2>Apply changes</h2>
        <p className="muted">Gmail mutations are disabled in this read-only preview mode. Every action will require explicit review before execution.</p>
        <button className="button" disabled>Approve &amp; apply ({proposals.length} proposals)</button>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><SidePanel /></React.StrictMode>);
