"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleHelp, ListChecks, RefreshCw, ShieldAlert, Target, UserRoundCheck } from "lucide-react";
import { authFetch } from "../lib/api";
import {
  WorkspaceEmpty, WorkspaceHeader, WorkspaceLoading, WorkspaceNotice,
  WorkspacePanel, WorkspaceStats,
} from "../../components/OutreachWorkspace";
import styles from "../../components/OutreachWorkspace.module.css";

export default function LeadQualityPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await authFetch("/api/lead-quality/");
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Could not load lead quality.");
      setData(payload);
    } catch (loadError) {
      setError(loadError.message || "Could not load lead quality.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const summary = data?.summary || {};

  return (
    <main>
      <WorkspaceHeader
        eyebrow="Lead workspace"
        title="Lead quality"
        description="See which leads are ready to contact and what information needs attention first."
        action={<div className={styles.headerAction}>
          <Link href="/prospecting" className={styles.button}><Target size={15} /> Find leads</Link>
          <button type="button" className={styles.secondaryButton} onClick={load} disabled={loading}><RefreshCw size={14} /> Refresh</button>
        </div>}
      />
      <WorkspaceNotice>
        “Verified” means Apollo or Hunter returned a provider-verified work email. Manually added addresses stay unchecked until you verify them. This view helps you review the record; it does not send messages or verify addresses itself.
      </WorkspaceNotice>
      {error && <WorkspaceNotice tone="warning">{error}</WorkspaceNotice>}

      {loading && !data ? <WorkspaceLoading label="Checking your lead records" /> : <>
        <WorkspaceStats items={[
          { label: "Total leads", value: summary.total ?? 0, detail: "In your lead database", icon: ListChecks },
          { label: "Ready to contact", value: summary.ready_to_contact ?? 0, detail: "Verified, pending, not suppressed", icon: UserRoundCheck },
          { label: "Provider verified", value: summary.verified ?? 0, detail: "Verified work email status", icon: CheckCircle2 },
          { label: "Needs attention", value: summary.needs_attention ?? 0, detail: `${summary.suppressed ?? 0} suppressed and excluded`, icon: ShieldAlert },
        ]} />
        <WorkspaceStats items={[
          { label: "High fit", value: summary.high_fit ?? 0, detail: "ICP score of 80 or above", icon: Target },
          { label: "Complete profiles", value: summary.complete_profiles ?? 0, detail: "Company, role, and website present", icon: CheckCircle2 },
          { label: "Not checked", value: summary.unknown ?? 0, detail: "Manual or unverified-source leads", icon: CircleHelp },
          { label: "Not verified", value: summary.not_verified ?? 0, detail: "Provider did not verify address", icon: ShieldAlert },
        ]} />
        <WorkspacePanel
          title="Review these leads"
          description="The list highlights common fixes. Suppressed leads are flagged so they are not mistaken for outreach-ready records."
          action={<Link href="/leads" className={styles.textLink}>Open leads database <span aria-hidden="true">→</span></Link>}
        >
          {!data?.attention_leads?.length ? (
            <WorkspaceEmpty title="Your lead records look complete" description="No leads currently match the quality checks. New records will appear here when something needs a review." href="/prospecting" actionLabel="Find more leads" />
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead><tr><th>Lead</th><th>Work email</th><th>Fit score</th><th>Next check</th></tr></thead>
                <tbody>{data.attention_leads.map((lead) => (
                  <tr key={lead.id}>
                    <td><span className={styles.primaryCell}>{lead.name || "Unnamed lead"}</span><span className={styles.secondaryCell}>{lead.company || "Company missing"}{lead.title ? ` · ${lead.title}` : ""}</span></td>
                    <td>{lead.email || "No email"}<span className={styles.secondaryCell}>{lead.email_status === "verified" ? "Provider verified" : lead.email_status === "not_verified" ? "Not verified" : "Not checked"}</span></td>
                    <td>{lead.icp_score ?? 0}/100</td>
                    <td><div className={styles.flagList}>{lead.flags.map((flag) => <span className={styles.flag} key={flag}>{flag}</span>)}</div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {(data?.attention_leads?.length || 0) >= 20 && <p className={styles.secondaryCell} style={{ marginTop: ".75rem" }}>Showing the latest 20 records that need attention. Open the leads database to review the full list.</p>}
        </WorkspacePanel>
        <div style={{ marginTop: "1rem" }}>
          <WorkspaceNotice tone="warning">
            {data?.verification_note || "Only provider-returned verification is shown. Review manually added addresses before contacting them."} Leads marked “Suppressed, do not contact” should remain excluded from outreach.
          </WorkspaceNotice>
        </div>
      </>}
    </main>
  );
}
