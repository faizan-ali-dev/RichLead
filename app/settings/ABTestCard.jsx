"use client";

import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Save, Loader2, Check, AlertCircle, Trophy } from "lucide-react";
import { authFetch } from "../lib/api";
import styles from "./page.module.css";

const pct = (r) => `${(r * 100).toFixed(1)}%`;

export default function ABTestCard() {
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await authFetch("/api/ai/subject-experiment/");
      if (res.ok) setForm(await res.json());
    } catch {
      setNotice({ type: "error", text: "Could not load the subject experiment." });
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async (status) => {
    setSaving(true);
    setNotice(null);
    try {
      const res = await authFetch("/api/ai/subject-experiment/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: status ?? form.status,
          variant_a_label: form.variant_a_label,
          variant_a_instruction: form.variant_a_instruction,
          variant_b_label: form.variant_b_label,
          variant_b_instruction: form.variant_b_instruction,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setNotice({ type: "error", text: Object.values(data).flat().join(" ") || "Could not save." });
      } else {
        setForm(data);
        setNotice({ type: "success", text: "Subject experiment saved." });
      }
    } catch {
      setNotice({ type: "error", text: "Network error while saving." });
    }
    setSaving(false);
  };

  if (!form) return null;

  const running = form.status === "running";
  const decided = form.status === "decided";
  const results = form.results || { a: {}, b: {} };

  const VariantResult = ({ v, label }) => {
    const r = results[v] || {};
    const won = decided && form.winner === v;
    return (
      <div className={`${styles.abResult} ${won ? styles.abWinner : ""}`}>
        <div className={styles.abResultHead}>
          {won && <Trophy size={13} />}
          <strong>{label}</strong>
        </div>
        <div className={styles.abResultStat}>{pct(r.reply_rate || 0)}</div>
        <div className={styles.abResultSub}>
          {r.replied || 0} / {r.sent || 0} replied
        </div>
      </div>
    );
  };

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>
        <FlaskConical size={20} className="text-accent-primary" />
        Subject A/B Test
      </h2>

      <p className={styles.hint}>
        Test two subject-writing approaches against each other. Each lead is randomly assigned an
        approach, and once one wins clearly, RichLead uses it for all new drafts. The body is never
        affected.
      </p>

      {decided && (
        <div className={styles.activeBanner}>
          <Trophy size={16} />
          <span>
            Winner decided: <strong>{form.winner === "a" ? form.variant_a_label : form.variant_b_label}</strong>.
            New drafts use it automatically.
          </span>
        </div>
      )}

      <div className={styles.twoCol}>
        <div className={styles.formGroup}>
          <label>Approach A name</label>
          <input className={styles.input} value={form.variant_a_label} onChange={set("variant_a_label")} />
          <textarea
            className={`${styles.input} ${styles.textareaSm}`}
            value={form.variant_a_instruction}
            onChange={set("variant_a_instruction")}
            placeholder="Write the subject as a short, specific question."
          />
        </div>
        <div className={styles.formGroup}>
          <label>Approach B name</label>
          <input className={styles.input} value={form.variant_b_label} onChange={set("variant_b_label")} />
          <textarea
            className={`${styles.input} ${styles.textareaSm}`}
            value={form.variant_b_instruction}
            onChange={set("variant_b_instruction")}
            placeholder="Write the subject as a plain statement of the problem."
          />
        </div>
      </div>

      {(running || decided) && (
        <div className={styles.abResults}>
          <VariantResult v="a" label={form.variant_a_label} />
          <VariantResult v="b" label={form.variant_b_label} />
        </div>
      )}

      <div className={styles.abButtons}>
        <button className={styles.saveBtn} onClick={() => save()} disabled={saving}>
          {saving ? <Loader2 size={18} className={styles.spin} /> : <Save size={18} />}
          Save
        </button>
        {running ? (
          <button className={styles.secondaryBtn} onClick={() => save("off")} disabled={saving}>
            Pause test
          </button>
        ) : (
          <button className={styles.secondaryBtn} onClick={() => save("running")} disabled={saving}>
            {decided ? "Run again" : "Start test"}
          </button>
        )}
      </div>

      {notice && (
        <div className={notice.type === "error" ? styles.errorBox : styles.successBox}>
          {notice.type === "error" ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{notice.text}</span>
        </div>
      )}
    </div>
  );
}
