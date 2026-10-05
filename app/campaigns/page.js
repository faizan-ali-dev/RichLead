"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Check, Pause, Play, RefreshCw, Settings2, StopCircle, XCircle } from "lucide-react";
import { authFetch } from "../lib/api";
import { useFeedback } from "../../components/FeedbackProvider";
import {
  StatusBadge, WorkspaceEmpty, WorkspaceHeader, WorkspaceLoading, WorkspaceNotice,
  WorkspacePanel, WorkspaceStats, formatWorkspaceDate,
} from "../../components/OutreachWorkspace";
import styles from "../../components/OutreachWorkspace.module.css";
import CampaignFunnels from "../../components/CampaignFunnels";

const initialSettings = { enabled: false, total_follow_ups: 2, days_between: 3, stop_on_reply: true };

export default function EmailSequencesPage() {
  const { notify, confirm } = useFeedback();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(initialSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workingId, setWorkingId] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const response = await authFetch("/api/integrations/sequences/");
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Could not load your email sequences.");
      setData(payload);
      setSettings(payload.settings || initialSettings);
    } catch (loadError) {
      setError(loadError.message || "Could not load your email sequences.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const saveSettings = async () => {
    setSaving(true);
    setError("");
    try {
      const response = await authFetch("/api/ai/followup-settings/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: settings.enabled,
          total_follow_ups: Number(settings.total_follow_ups),
          days_between: Number(settings.days_between),
          stop_on_reply: settings.stop_on_reply,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Could not save the sequence settings.");
      setSettings(payload);
      setData((current) => current ? { ...current, settings: payload, readiness: { ...current.readiness, follow_ups_enabled: payload.enabled && payload.total_follow_ups > 0 } } : current);
      notify("Your email sequence settings have been saved.", { type: "success", title: "Settings saved" });
    } catch (saveError) {
      setError(saveError.message || "Could not save the sequence settings.");
    } finally {
      setSaving(false);
    }
  };

  const updateSequence = async (sequence, action) => {
    if (action === "stop") {
      const accepted = await confirm({
        title: "Stop this sequence?",
        message: `No more scheduled follow-ups will be sent to ${sequence.lead.name || sequence.lead.email}.`,
        confirmLabel: "Stop sequence",
        variant: "danger",
      });
      if (!accepted) return;
    }
    setWorkingId(sequence.id);
    try {
      const response = await authFetch(`/api/integrations/sequences/${sequence.id}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Could not update this sequence.");
      notify(action === "stop" ? "The sequence has been stopped." : `The sequence has been ${action === "pause" ? "paused" : "resumed"}.`, { type: "success" });
      await load();
    } catch (actionError) {
      notify(actionError.message || "Could not update this sequence.", { type: "error", title: "Sequence not updated" });
    } finally {
      setWorkingId(null);
    }
  };

  const counts = data?.counts || {};
  const readiness = data?.readiness || {};

  return (
    <main>
      <WorkspaceHeader
        eyebrow="Outreach"
        title="Email sequences"
        description="Set a simple follow-up rhythm, then see what is scheduled and pause or stop it whenever you need."
        action={<button type="button" className={styles.secondaryButton} onClick={load} disabled={loading}><RefreshCw size={14} /> Refresh</button>}
      />
      <WorkspaceNotice>
        A sequence starts after you send the first email to a lead. RichLead schedules the follow-ups you choose and stops them when a reply is received, the lead is suppressed, or you stop the sequence.
      </WorkspaceNotice>
      {error && <WorkspaceNotice tone="warning">{error}</WorkspaceNotice>}

      {loading && !data ? <WorkspaceLoading label="Loading your sequences" /> : <>
        <WorkspaceStats items={[
          { label: "Active", value: counts.active ?? 0, detail: "Scheduled to continue", icon: Play },
          { label: "Paused", value: counts.paused ?? 0, detail: "Waiting for you", icon: Pause },
          { label: "Completed", value: counts.completed ?? 0, detail: "All planned steps sent", icon: Check },
          { label: "Needs review", value: counts.needs_review ?? 0, detail: "Could not be sent", icon: XCircle },
        ]} />

        <CampaignFunnels />

        <div className={styles.twoColumn}>
          <WorkspacePanel title="Your sequence" description={`${data?.total ?? 0} lead${data?.total === 1 ? "" : "s"} in a sequence · ${counts.stopped ?? 0} stopped. Active schedules appear first.`}>
            {!data?.items?.length ? (
              <WorkspaceEmpty
                title="No email sequences yet"
                description="Send a first email to a lead with follow-ups enabled. RichLead will create its schedule automatically."
                href="/leads"
                actionLabel="Open your leads"
              />
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead><tr><th>Lead</th><th>Progress</th><th>Next follow-up</th><th>Status</th><th>Manage</th></tr></thead>
                  <tbody>{data.items.map((sequence) => (
                    <tr key={sequence.id}>
                      <td><span className={styles.primaryCell}>{sequence.lead.name || "Unnamed lead"}</span><span className={styles.secondaryCell}>{sequence.lead.company || sequence.lead.email}</span></td>
                      <td>Step {Math.min(sequence.next_step, sequence.total_follow_ups)} of {sequence.total_follow_ups || 0}</td>
                      <td>{sequence.status === "active" || sequence.status === "paused" ? formatWorkspaceDate(sequence.next_send_at) : "—"}</td>
                      <td><StatusBadge status={sequence.status} /></td>
                      <td><div className={styles.inlineActions}>
                        {sequence.status === "active" && <button type="button" className={styles.secondaryButton} disabled={workingId === sequence.id} onClick={() => updateSequence(sequence, "pause")} aria-label={`Pause sequence for ${sequence.lead.name}`}><Pause size={14} /> Pause</button>}
                        {sequence.status === "paused" && <button type="button" className={styles.secondaryButton} disabled={workingId === sequence.id} onClick={() => updateSequence(sequence, "resume")} aria-label={`Resume sequence for ${sequence.lead.name}`}><Play size={14} /> Resume</button>}
                        {(sequence.status === "active" || sequence.status === "paused") && <button type="button" className={styles.dangerButton} disabled={workingId === sequence.id} onClick={() => updateSequence(sequence, "stop")} aria-label={`Stop sequence for ${sequence.lead.name}`}><StopCircle size={14} /> Stop</button>}
                      </div></td>
                    </tr>
                  ))}</tbody>
                </table>
                {data.has_more && <p className={styles.tableFootnote}>Showing the next 100 scheduled sequences.</p>}
              </div>
            )}
          </WorkspacePanel>

          <div>
            <WorkspacePanel title="Sequence settings" description="Changes here apply to future follow-ups. Existing schedules keep their current next-send time.">
              <div className={styles.checkList} style={{ marginBottom: "1rem" }}>
                <div className={styles.checkItem}><span className={readiness.sender_connected ? styles.checkPass : styles.checkTodo}>{readiness.sender_connected ? "✓" : "•"}</span>{readiness.sender_connected ? `${readiness.connected_sender_count} sender account${readiness.connected_sender_count === 1 ? "" : "s"} connected` : <Link href="/senders" className={styles.textLink}>Connect a sender account</Link>}</div>
                <div className={styles.checkItem}><span className={readiness.ai_connected ? styles.checkPass : styles.checkTodo}>{readiness.ai_connected ? "✓" : "•"}</span>{readiness.ai_connected ? "Primary AI provider is ready" : <Link href="/settings/ai" className={styles.textLink}>Set up an AI provider</Link>}</div>
              </div>
              <div className={styles.formGrid}>
                <label className={styles.field}>Follow-ups after first email
                  <select className={styles.select} value={settings.total_follow_ups} onChange={(event) => setSettings({ ...settings, total_follow_ups: Number(event.target.value) })}>
                    {[0, 1, 2, 3, 4, 5].map((count) => <option key={count} value={count}>{count === 0 ? "No follow-ups" : `${count} follow-up${count === 1 ? "" : "s"}`}</option>)}
                  </select>
                  <small>Choose a short, considerate sequence.</small>
                </label>
                <label className={styles.field}>Days between messages
                  <select className={styles.select} value={settings.days_between} onChange={(event) => setSettings({ ...settings, days_between: Number(event.target.value) })}>
                    {[2, 3, 4, 5, 7, 10, 14].map((days) => <option key={days} value={days}>{days} days</option>)}
                  </select>
                  <small>The delay between follow-up steps.</small>
                </label>
              </div>
              <label className={styles.checkRow} style={{ marginTop: ".9rem" }}><input type="checkbox" checked={settings.enabled} onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })} />Enable follow-ups for new sends</label>
              <label className={styles.checkRow} style={{ marginTop: ".7rem" }}><input type="checkbox" checked={settings.stop_on_reply} onChange={(event) => setSettings({ ...settings, stop_on_reply: event.target.checked })} />Stop a sequence as soon as the lead replies</label>
              <div className={styles.saveRow}>
                <span className={styles.secondaryCell}>You can still pause or stop individual leads above.</span>
                <button type="button" className={styles.button} onClick={saveSettings} disabled={saving}>{saving ? "Saving…" : <><Settings2 size={15} /> Save settings</>}</button>
              </div>
            </WorkspacePanel>
            <WorkspaceNotice tone="warning">
              Follow-ups depend on a connected sending mailbox and the configured schedule. Check the deliverability page before increasing sending volume.
            </WorkspaceNotice>
          </div>
        </div>
      </>}
    </main>
  );
}
