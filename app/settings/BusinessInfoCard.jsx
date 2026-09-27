"use client";

import { useCallback, useEffect, useState } from "react";
import { Briefcase, Save, Loader2, Check, AlertCircle } from "lucide-react";
import { authFetch } from "../lib/api";
import styles from "./page.module.css";

const BLANK = {
  company_name: "",
  website: "",
  industry: "",
  what_you_do: "",
  problem_you_solve: "",
  ideal_customer: "",
  differentiator: "",
  proof_points: "",
  case_study: "",
  never_claim: "",
  sender_name: "",
  sender_title: "",
};

export default function BusinessInfoCard() {
  const [form, setForm] = useState(BLANK);
  const [complete, setComplete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await authFetch("/api/ai/business-profile/");
      if (res.ok) {
        const data = await res.json();
        setForm({ ...BLANK, ...data });
        setComplete(data.is_complete);
      }
    } catch {
      setNotice({ type: "error", text: "Could not load your business information." });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const res = await authFetch("/api/ai/business-profile/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) {
        setNotice({ type: "error", text: Object.values(data).flat().join(" ") || "Could not save." });
      } else {
        setComplete(data.is_complete);
        setNotice({ type: "success", text: "Saved. New drafts will pitch using this." });
      }
    } catch {
      setNotice({ type: "error", text: "Network error while saving." });
    }
    setSaving(false);
  };

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>
        <Briefcase size={20} className="text-accent-primary" />
        Business Information
      </h2>

      {complete ? (
        <div className={styles.activeBanner}>
          <Check size={16} />
          <span>The AI has what it needs to pitch your business accurately.</span>
        </div>
      ) : (
        <div className={styles.warnBanner}>
          <AlertCircle size={16} />
          <span>
            Fill in at least <strong>what you do</strong> and <strong>the problem you solve</strong>.
            Without them the AI invents a pitch, which is the main cause of generic emails.
          </span>
        </div>
      )}

      <p className={styles.hint}>
        Everything here is given to the AI before it writes. It may only pitch what you state,
        so be specific and truthful.
      </p>

      <div className={styles.twoCol}>
        <div className={styles.formGroup}>
          <label>Company name</label>
          <input className={styles.input} value={form.company_name} onChange={set("company_name")} placeholder="Acme" />
        </div>
        <div className={styles.formGroup}>
          <label>Industry</label>
          <input className={styles.input} value={form.industry} onChange={set("industry")} placeholder="B2B SaaS" />
        </div>
      </div>

      <div className={styles.formGroup}>
        <label>Website</label>
        <input className={styles.input} value={form.website} onChange={set("website")} placeholder="acme.com" />
      </div>

      <div className={styles.formGroup}>
        <label>What you do</label>
        <textarea
          className={`${styles.input} ${styles.textarea}`}
          value={form.what_you_do}
          onChange={set("what_you_do")}
          placeholder="Say it the way you would out loud. We cut the time SDR teams spend building lists from about an hour a day to ten minutes."
        />
      </div>

      <div className={styles.formGroup}>
        <label>The problem you solve</label>
        <textarea
          className={`${styles.input} ${styles.textarea}`}
          value={form.problem_you_solve}
          onChange={set("problem_you_solve")}
          placeholder="SDRs lose the first hour of every day to manual research instead of talking to prospects."
        />
        <span className={styles.fieldHint}>
          Every email opens on the prospect&apos;s version of this problem.
        </span>
      </div>

      <div className={styles.formGroup}>
        <label>Who you sell to</label>
        <textarea
          className={`${styles.input} ${styles.textareaSm}`}
          value={form.ideal_customer}
          onChange={set("ideal_customer")}
          placeholder="Heads of Sales and SDR managers at 20 to 200 person B2B software companies."
        />
      </div>

      <div className={styles.formGroup}>
        <label>Why you rather than the alternative</label>
        <textarea
          className={`${styles.input} ${styles.textareaSm}`}
          value={form.differentiator}
          onChange={set("differentiator")}
          placeholder="Sets up in ten minutes with no data team, where the alternatives need a month of onboarding."
        />
      </div>

      <div className={styles.formGroup}>
        <label>Proof points</label>
        <textarea
          className={`${styles.input} ${styles.textareaSm}`}
          value={form.proof_points}
          onChange={set("proof_points")}
          placeholder={"One per line.\nTook Loop from a 4% to an 11% reply rate in six weeks."}
        />
        <span className={styles.fieldHint}>Concrete and checkable beats impressive-sounding.</span>
      </div>

      <div className={styles.formGroup}>
        <label>Customer story the AI may reference</label>
        <textarea
          className={`${styles.input} ${styles.textareaSm}`}
          value={form.case_study}
          onChange={set("case_study")}
          placeholder="Loop had three SDRs spending mornings on lists. Two weeks after switching they were booking 40% more calls."
        />
      </div>

      <div className={styles.formGroup}>
        <label>Never claim</label>
        <textarea
          className={`${styles.input} ${styles.textareaSm}`}
          value={form.never_claim}
          onChange={set("never_claim")}
          placeholder="SOC 2 certification, HIPAA compliance, named customers we cannot reference publicly."
        />
        <span className={styles.fieldHint}>
          Hard guardrail. The AI will not make these claims even if they would strengthen the pitch.
        </span>
      </div>

      <div className={styles.twoCol}>
        <div className={styles.formGroup}>
          <label>Your name</label>
          <input className={styles.input} value={form.sender_name} onChange={set("sender_name")} placeholder="Sridhar" />
        </div>
        <div className={styles.formGroup}>
          <label>Your title</label>
          <input className={styles.input} value={form.sender_title} onChange={set("sender_title")} placeholder="Founder" />
        </div>
      </div>

      <button className={styles.saveBtn} onClick={save} disabled={saving}>
        {saving ? <Loader2 size={18} className={styles.spin} /> : <Save size={18} />}
        {saving ? "Saving..." : "Save Business Information"}
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
