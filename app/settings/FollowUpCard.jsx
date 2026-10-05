"use client";

import { useCallback, useEffect, useState } from "react";
import { Repeat, Save, Loader2, Check, AlertCircle } from "lucide-react";
import { authFetch } from "../lib/api";
import styles from "./page.module.css";

const OPT_OUT_MODES = [
  {
    value: "text",
    title: "Plain-text line in the body",
    detail:
      "A sentence asking them to reply if they want out. Compliant, and the best choice for landing in the Primary tab. Recommended below ~5,000 emails/day.",
  },
  {
    value: "header",
    title: "List-Unsubscribe header only",
    detail:
      "Required by Gmail and Yahoo above ~5,000 emails/day. Below that it mostly signals bulk mail, which files you under Promotions.",
  },
  { value: "both", title: "Both", detail: "Maximum compliance, highest Promotions-tab risk." },
];

export default function FollowUpCard() {
  const [form, setForm] = useState(null);
  const [optOutMode, setOptOutMode] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      const [followRes, settingsRes] = await Promise.all([
        authFetch("/api/ai/followup-settings/"),
        authFetch("/api/users/settings/"),
      ]);
      if (followRes.ok) setForm(await followRes.json());
      if (settingsRes.ok) setOptOutMode((await settingsRes.json()).unsubscribe_mode);
    } catch {
      setNotice({ type: "error", text: "Could not load follow-up settings." });
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const res = await authFetch("/api/ai/followup-settings/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: form.enabled,
          total_follow_ups: Number(form.total_follow_ups),
          days_between: Number(form.days_between),
          stop_on_reply: form.stop_on_reply,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setNotice({ type: "error", text: Object.values(data).flat().join(" ") || "Could not save." });
      } else {
        setForm(data);
        setNotice({ type: "success", text: "Follow-up settings saved." });
      }
    } catch {
      setNotice({ type: "error", text: "Network error while saving." });
    }
    setSaving(false);
  };

  const changeOptOut = async (value) => {
    setOptOutMode(value);
    await authFetch("/api/users/settings/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ unsubscribe_mode: value }),
    });
  };

  if (!form) return null;

  const schedule = [];
  for (let i = 0; i <= form.total_follow_ups; i += 1) {
    schedule.push(i === 0 ? "First email" : `Follow-up ${i}: day ${i * form.days_between}`);
  }

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>
        <Repeat size={20} className="text-accent-primary" />
        Follow-ups
      </h2>

      <p className={styles.hint}>
        Most replies to cold email come from a follow-up, not the first message. Two or three
        follow-ups spaced a few days apart is the sweet spot; beyond that replies fall and
        complaints rise.
      </p>

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
        />
        <span>
          <strong>Send follow-ups</strong>
          <p>Turn off to send a single email per lead and stop.</p>
        </span>
      </label>

      <div className={styles.twoCol}>
        <div className={styles.formGroup}>
          <label>How many follow-ups</label>
          <select
            className={styles.input}
            value={form.total_follow_ups}
            onChange={(e) => setForm({ ...form, total_follow_ups: Number(e.target.value) })}
            disabled={!form.enabled}
          >
            {[0, 1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n === 0 ? "None, send once" : `${n} follow-up${n > 1 ? "s" : ""}`}
              </option>
            ))}
          </select>
          <span className={styles.fieldHint}>After the first email.</span>
        </div>

        <div className={styles.formGroup}>
          <label>Days between each</label>
          <select
            className={styles.input}
            value={form.days_between}
            onChange={(e) => setForm({ ...form, days_between: Number(e.target.value) })}
            disabled={!form.enabled}
          >
            {[2, 3, 4, 5, 7, 10, 14].map((n) => (
              <option key={n} value={n}>
                {n} days
              </option>
            ))}
          </select>
          <span className={styles.fieldHint}>Under 2 days reads as automated.</span>
        </div>
      </div>

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={form.stop_on_reply}
          onChange={(e) => setForm({ ...form, stop_on_reply: e.target.checked })}
        />
        <span>
          <strong>Stop when they reply</strong>
          <p>Following up after someone has already answered is the fastest way to a complaint.</p>
        </span>
      </label>

      {form.enabled && (
        <div className={styles.schedulePreview}>
          <span className={styles.scheduleLabel}>Schedule per lead</span>
          <ul>
            {schedule.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      )}

      <button className={styles.saveBtn} onClick={save} disabled={saving}>
        {saving ? <Loader2 size={18} className={styles.spin} /> : <Save size={18} />}
        {saving ? "Saving..." : "Save Follow-up Settings"}
      </button>

      {notice && (
        <div className={notice.type === "error" ? styles.errorBox : styles.successBox}>
          {notice.type === "error" ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{notice.text}</span>
        </div>
      )}

      {optOutMode && (
        <div className={styles.optOut}>
          <h3 className={styles.subTitle}>Opt-out method</h3>
          <p className={styles.hint} style={{ marginBottom: "0.9rem" }}>
            Every option keeps you compliant. The header protects you from the spam folder at bulk
            volume but pushes Gmail to file you under Promotions.
          </p>
          <div className={styles.modeRow}>
            {OPT_OUT_MODES.map((mode) => (
              <label
                key={mode.value}
                className={`${styles.modeOption} ${optOutMode === mode.value ? styles.modeSelected : ""}`}
              >
                <input
                  type="radio"
                  name="optOutMode"
                  checked={optOutMode === mode.value}
                  onChange={() => changeOptOut(mode.value)}
                />
                <span>
                  <strong>{mode.title}</strong>
                  <p>{mode.detail}</p>
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
