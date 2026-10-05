"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, RefreshCw } from "lucide-react";
import { authFetch } from "../app/lib/api";
import { WorkspacePanel } from "./OutreachWorkspace";
import styles from "./OutreachWorkspace.module.css";

const pct = (r) => `${((r || 0) * 100).toFixed(1)}%`;

// Reply rate drives the colour so a weak campaign or inbox stands out.
const rateColor = (r) => {
  if (r >= 0.1) return "var(--accent-success)";
  if (r >= 0.03) return "#eab308";
  return "var(--accent-danger)";
};

export default function CampaignFunnels() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch("/api/analytics/campaigns/");
      if (res.ok) setData(await res.json());
    } catch {
      setData(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const campaigns = data?.campaigns || [];
  const mailboxes = data?.mailboxes || [];
  const hasData = campaigns.length > 0 || mailboxes.length > 0;

  return (
    <WorkspacePanel
      title="Performance"
      description="Reply funnels by campaign and by sending inbox. A low reply rate on one inbox is an early deliverability warning."
      action={
        <button type="button" className={styles.secondaryButton} onClick={load} disabled={loading}>
          <RefreshCw size={14} /> Refresh
        </button>
      }
    >
      {!hasData ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          {loading ? "Loading performance…" : "No sends yet. Analytics appear once you start emailing leads."}
        </p>
      ) : (
        <div className={styles.twoColumn}>
          <div>
            <h4 style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.6rem" }}>
              <BarChart3 size={15} /> By campaign
            </h4>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Campaign</th>
                    <th>Sent</th>
                    <th>Replied</th>
                    <th>Reply rate</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c) => (
                    <tr key={c.label}>
                      <td><span className={styles.primaryCell}>{c.label}</span></td>
                      <td>{c.sent}</td>
                      <td>{c.replied}</td>
                      <td style={{ color: rateColor(c.reply_rate), fontWeight: 600 }}>{pct(c.reply_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h4 style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.6rem" }}>
              <BarChart3 size={15} /> By sending inbox
            </h4>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Mailbox</th>
                    <th>Sent</th>
                    <th>Replied</th>
                    <th>Reply rate</th>
                  </tr>
                </thead>
                <tbody>
                  {mailboxes.length === 0 ? (
                    <tr><td colSpan={4} style={{ color: "var(--text-muted)" }}>No mailbox sends yet.</td></tr>
                  ) : (
                    mailboxes.map((m) => (
                      <tr key={m.label}>
                        <td><span className={styles.primaryCell}>{m.label}</span></td>
                        <td>{m.sent}</td>
                        <td>{m.replied}</td>
                        <td style={{ color: rateColor(m.reply_rate), fontWeight: 600 }}>{pct(m.reply_rate)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </WorkspacePanel>
  );
}
