"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock, Save, Loader2, Check, AlertCircle } from "lucide-react";
import { authFetch } from "../lib/api";
import styles from "./page.module.css";

const HOURS = Array.from({ length: 24 }, (_, h) => h);
const fmtHour = (h) => {
  const period = h < 12 ? "AM" : "PM";
  const display = h % 12 === 0 ? 12 : h % 12;
  return `${display}:00 ${period}`;
};

export default function SendTimeCard() {
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await authFetch("/api/integrations/sending-window/");
      if (res.ok) setForm(await res.json());
    } catch {
      setNotice({ type: "error", text: "Could not load send-time settings." });
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
      const res = await authFetch("/api/integrations/sending-window/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          optimize_send_time: form.optimize_send_time,
          earliest_hour: Number(form.earliest_hour),
          latest_hour: Number(form.latest_hour),
          weekdays_only: form.weekdays_only,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setNotice({ type: "error", text: Object.values(data).flat().join(" ") || "Could not save." });
      } else {
        setForm(data);
        setNotice({ type: "success", text: "Send-time settings saved." });
      }
    } catch {
      setNotice({ type: "error", text: "Network error while saving." });
    }
    setSaving(false);
  };

  if (!form) return null;

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>
        <Clock size={20} className="text-accent-primary" />
        Send-Time Optimization
      </h2>

      <p className={styles.hint}>
        When on, approved emails are held and delivered during business hours in each
        recipient&apos;s local timezone (inferred from their location), rather than the moment you
        approve. Mail read in the morning gets far more replies than mail that lands overnight.
      </p>

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={form.optimize_send_time}
          onChange={(e) => setForm({ ...form, optimize_send_time: e.target.checked })}
        />
        <span>
          <strong>Optimize send time</strong>
          <p>Approving a draft schedules it for the recipient&apos;s next business morning.</p>
        </span>
      </label>

      <div className={styles.twoCol}>
        <div className={styles.formGroup}>
          <label>Earliest hour (recipient local)</label>
          <select
            className={styles.input}
            value={form.earliest_hour}
            onChange={(e) => setForm({ ...form, earliest_hour: Number(e.target.value) })}
            disabled={!form.optimize_send_time}
          >
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {fmtHour(h)}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.formGroup}>
          <label>Latest hour (recipient local)</label>
          <select
            className={styles.input}
            value={form.latest_hour}
            onChange={(e) => setForm({ ...form, latest_hour: Number(e.target.value) })}
            disabled={!form.optimize_send_time}
          >
            {HOURS.slice(1).concat(24).map((h) => (
              <option key={h} value={h}>
                {h === 24 ? "12:00 AM (next day)" : fmtHour(h)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={form.weekdays_only}
          onChange={(e) => setForm({ ...form, weekdays_only: e.target.checked })}
          disabled={!form.optimize_send_time}
        />
        <span>
          <strong>Weekdays only</strong>
          <p>Hold weekend sends until Monday morning. Cold email sent on weekends rarely gets read.</p>
        </span>
      </label>

      <button className={styles.saveBtn} onClick={save} disabled={saving}>
        {saving ? <Loader2 size={18} className={styles.spin} /> : <Save size={18} />}
        {saving ? "Saving..." : "Save Send-Time Settings"}
      </button>

      {notice && (
        <div className={notice.type === "error" ? styles.errorBox : styles.successBox}>
          {notice.type === "error" ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{notice.text}</span>
        </div>
      )}
    </div>
  );
}
