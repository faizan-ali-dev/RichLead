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

const AUTH_LABEL = {
  pass: "Pass", found: "Found", missing: "Missing", not_found: "Not found",
  unknown: "Unknown", error: "Check failed",
};

// Map a per-record check to a StatusBadge tone the design system already styles.
function authBadgeStatus(value) {
  if (value === "pass" || value === "found") return "connected";
  if (value === "missing" || value === "not_found") return "disconnected";
  return "near_limit";
}

export default function DeliverabilityPage() {
  const [period, setPeriod] = useState("30d");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rechecking, setRechecking] = useState(false);
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

  const recheckDomains = useCallback(async () => {
    setRechecking(true);
    setError("");
    try {
      const response = await authFetch("/api/integrations/deliverability/", { method: "POST" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Could not run the authentication check.");
      // Fold the fresh domain results into the loaded dashboard without a full reload.
      setData((prev) => (prev ? {
        ...prev,
        domains: payload.domains,
        domain_alerts: payload.domain_alerts,
        summary: { ...prev.summary, domain_alerts: payload.domain_alerts.length },
      } : prev));
    } catch (recheckError) {
      setError(recheckError.message || "Could not run the authentication check.");
    } finally {
      setRechecking(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { load(period); }, 0);
    return () => window.clearTimeout(timer);
  }, [load, period]);

  const summary = data?.summary || {};
  const domains = data?.domains || [];
  const domainAlerts = data?.domain_alerts || [];

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

        {domainAlerts.length > 0 && (
          <div style={{ marginTop: "1rem" }}>
            <WorkspaceNotice tone="warning">
              <strong>Deliverability drift detected.</strong>
              <ul style={{ margin: ".4rem 0 0", paddingLeft: "1.1rem" }}>
                {domainAlerts.map((alert) => (
                  <li key={alert.domain}>{alert.message}</li>
                ))}
              </ul>
            </WorkspaceNotice>
          </div>
        )}

        <WorkspacePanel
          title="Domain authentication"
          description="SPF, DKIM, and DMARC records for the domains you send from. If these change after a mailbox is warmed up, delivery can quietly drop — RichLead re-checks them automatically and flags any drift."
          action={<button type="button" className={styles.secondaryButton} onClick={recheckDomains} disabled={rechecking}><RefreshCw size={14} /> {rechecking ? "Checking…" : "Re-check now"}</button>}
        >
          {!domains.length ? (
            <WorkspaceEmpty
              title="No sending domains checked yet"
              description="Connect a mailbox, then run a check to see its SPF, DKIM, and DMARC status."
              href="/senders"
              actionLabel="Connect a sender"
            />
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead><tr><th>Domain</th><th>Overall</th><th>SPF</th><th>DKIM</th><th>DMARC</th><th>Notes</th></tr></thead>
                <tbody>{domains.map((domain) => (
                  <tr key={domain.domain}>
                    <td><span className={styles.primaryCell}>{domain.domain}</span></td>
                    <td><StatusBadge status={domain.status} /></td>
                    <td><StatusBadge status={authBadgeStatus(domain.spf_status)}>{AUTH_LABEL[domain.spf_status] || domain.spf_status}</StatusBadge></td>
                    <td><StatusBadge status={authBadgeStatus(domain.dkim_status)}>{AUTH_LABEL[domain.dkim_status] || domain.dkim_status}</StatusBadge></td>
                    <td>
                      <StatusBadge status={authBadgeStatus(domain.dmarc_status)}>{AUTH_LABEL[domain.dmarc_status] || domain.dmarc_status}</StatusBadge>
                      {domain.dmarc_policy && <span className={styles.secondaryCell}>p={domain.dmarc_policy}</span>}
                    </td>
                    <td>
                      {domain.issues?.length ? (
                        <ul style={{ margin: 0, paddingLeft: "1rem", fontSize: ".8rem", color: "var(--text-secondary)" }}>
                          {domain.issues.map((issue, index) => <li key={index}>{issue}</li>)}
                        </ul>
                      ) : <span className={styles.secondaryCell}>No issues found</span>}
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
