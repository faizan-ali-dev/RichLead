"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, AlertTriangle, Mail, MessageSquareReply, RefreshCw, ShieldCheck } from "lucide-react";
import { authFetch } from "../lib/api";
import {
  StatusBadge, WorkspaceEmpty, WorkspaceHeader, WorkspaceLoading, WorkspaceNotice,
  WorkspacePanel, WorkspaceStats,
} from "../../components/OutreachWorkspace";
import styles from "../../components/OutreachWorkspace.module.css";

function percent(value) {
  return value == null ? "—" : `${Number(value).toFixed(1)}%`;
}

export default function DeliverabilityPage() {
  const [period, setPeriod] = useState("30d");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (selectedPeriod = period) => {
    setLoading(true);
    setError("");
    try {
      const response = await authFetch(`/api/integrations/deliverability/?period=${selectedPeriod}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Could not load deliverability data.");
      setData(payload);
    } catch (loadError) {
      setError(loadError.message || "Could not load deliverability data.");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    const timer = window.setTimeout(() => { load(period); }, 0);
    return () => window.clearTimeout(timer);
  }, [load, period]);

  const summary = data?.summary || {};

  return (
    <main>
      <WorkspaceHeader
        eyebrow="Outreach health"
        title="Deliverability"
        description="A clear view of sending activity, mailbox limits, and the mail events RichLead has recorded."
        action={<div className={styles.headerAction}>
          <select className={styles.select} aria-label="Reporting period" value={period} onChange={(event) => setPeriod(event.target.value)}>
            <option value="7d">Last 7 days</option><option value="30d">Last 30 days</option>
          </select>
          <button type="button" className={styles.secondaryButton} onClick={() => load(period)} disabled={loading}><RefreshCw size={14} /> Refresh</button>
        </div>}
      />
      <WorkspaceNotice>
        Use these numbers to pace outreach. Reply rate is based on recorded email messages. Bounce and complaint counts only include events saved to your suppression list. RichLead does not currently track opens or clicks.
      </WorkspaceNotice>
      {error && <WorkspaceNotice tone="warning">{error}</WorkspaceNotice>}

      {loading && !data ? <WorkspaceLoading label="Loading mailbox health" /> : <>
        <WorkspaceStats items={[
          { label: "Emails sent", value: summary.sent ?? 0, detail: `During the last ${period === "7d" ? "7" : "30"} days`, icon: Mail },
          { label: "Replies", value: summary.replies ?? 0, detail: "Inbound replies linked to leads", icon: MessageSquareReply },
          { label: "Reply rate", value: percent(summary.reply_rate), detail: "Replies divided by sent emails", icon: Activity },
          { label: "Recorded bounces", value: summary.recorded_bounces ?? 0, detail: `${percent(summary.recorded_bounce_rate)} of sent emails`, icon: AlertTriangle },
          { label: "Recorded complaints", value: summary.complaints ?? 0, detail: "Saved to your suppression list", icon: ShieldCheck },
        ]} />

        <WorkspacePanel
          title="Mailbox health"
          description={`${summary.connected_senders ?? 0} of ${summary.total_senders ?? 0} mailboxes connected. Daily usage resets according to your account's local date.`}
        >
          {!data?.senders?.length ? (
            <WorkspaceEmpty title="No sender accounts yet" description="Connect a mailbox to begin sending and monitor its daily sending limit here." href="/senders" actionLabel="Connect a sender" />
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead><tr><th>Mailbox</th><th>Connection</th><th>Sent today</th><th>Daily limit</th><th>Remaining</th><th>Health</th></tr></thead>
                <tbody>{data.senders.map((sender) => (
                  <tr key={sender.id}>
                    <td><span className={styles.primaryCell}>{sender.email}</span><span className={styles.secondaryCell}>{sender.provider}</span></td>
                    <td><StatusBadge status={sender.connected ? "connected" : "disconnected"}>{sender.connected ? "Connected" : "Disconnected"}</StatusBadge></td>
                    <td>{sender.sent_today}</td>
                    <td>{sender.daily_limit}</td>
                    <td>{sender.remaining_today}</td>
                    <td>
                      <StatusBadge status={sender.status} />
                      <div className={styles.progressTrack} role="progressbar" aria-label={`${sender.email} daily send usage`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={sender.usage_percent}>
                        <div className={styles.progressFill} style={{ width: `${Math.min(100, Math.max(0, sender.usage_percent))}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </WorkspacePanel>

        <div style={{ marginTop: "1rem" }}>
          <WorkspaceNotice tone="warning">
            A green status means the mailbox is connected and below its configured daily limit. It does not guarantee inbox placement. Review provider warnings and keep your sending volume gradual.
          </WorkspaceNotice>
        </div>
        <div className={styles.inlineActions} style={{ justifyContent: "flex-start", marginTop: ".75rem" }}>
          <Link href="/senders" className={styles.secondaryButton}><ShieldCheck size={14} /> Manage sender accounts</Link>
        </div>
      </>}
    </main>
  );
}
