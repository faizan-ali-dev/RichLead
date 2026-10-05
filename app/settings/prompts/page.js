"use client";

import styles from "./page.module.css";
import { Bot, Save, Lock, ShieldCheck, Beaker, Loader2, AlertCircle, Check } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import SettingsModule from "@/components/SettingsModule";
import { authFetch, asList } from "../../lib/api";
import ABTestCard from "../ABTestCard";

const TONES = [
  "Direct and professional",
  "Warm and conversational",
  "Blunt and to the point",
  "Curious and consultative",
];

const BLANK = {
  name: "Default Outreach",
  system_prompt: "",
  tone_of_voice: TONES[0],
  sender_role: "",
  value_proposition: "",
  proof_point: "",
  call_to_action: "",
  avoid_topics: "",
};

const SEVERITY_COLOR = {
  high: "var(--accent-danger)",
  medium: "#eab308",
  low: "var(--text-secondary)",
};

export default function PromptsSettingsPage() {
  const [form, setForm] = useState(BLANK);
  const [templateId, setTemplateId] = useState(null);
  const [rules, setRules] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  // Live spam tester
  const [testSubject, setTestSubject] = useState("");
  const [testBody, setTestBody] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [promptRes, rulesRes] = await Promise.all([
        authFetch("/api/ai/prompts/"),
        authFetch("/api/ai/prompt-rules/"),
      ]);
      if (promptRes.ok) {
        const active = asList(await promptRes.json()).find((t) => t.is_active);
        if (active) {
          setTemplateId(active.id);
          setForm({ ...BLANK, ...active });
        }
      }
      if (rulesRes.ok) setRules(await rulesRes.json());
    } catch {
      setNotice({ type: "error", text: "Could not load prompt settings." });
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const res = await authFetch(
        templateId ? `/api/ai/prompts/${templateId}/` : "/api/ai/prompts/",
        {
          method: templateId ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...form, is_active: true }),
        }
      );
      const data = await res.json();
      if (!res.ok) {
        setNotice({ type: "error", text: Object.values(data).flat().join(" ") || "Could not save." });
      } else {
        setTemplateId(data.id);
        setNotice({ type: "success", text: "Prompt settings saved. New drafts will use them." });
      }
    } catch {
      setNotice({ type: "error", text: "Network error while saving." });
    }
    setSaving(false);
  };

  const runSpamCheck = async () => {
    setTesting(true);
    try {
      const res = await authFetch("/api/ai/spam-check/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject: testSubject, body: testBody }),
      });
      if (res.ok) setTestResult(await res.json());
    } catch {
      setTestResult(null);
    }
    setTesting(false);
  };

  const gradeColor = (grade) =>
    grade === "excellent" || grade === "good"
      ? "var(--accent-success)"
      : grade === "needs work"
      ? "#eab308"
      : "var(--accent-danger)";

  return (
    <SettingsModule title="Prompts" description="Control the instructions and tone RichLead uses when drafting outreach.">
      <div className={styles.page}>
      <div className={`${styles.column} animate-fade-in`}>
        {/* ---- Editable instructions ---- */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <Bot size={20} className="text-accent-primary" />
              Your Instructions
            </h2>
            <p className={styles.cardSubtitle}>
              These shape what the AI writes. The safety and anti-spam rules below are always applied on top.
            </p>
          </div>

          <div className={styles.formGroup}>
            <label>Instructions to the AI</label>
            <textarea
              className={`${styles.input} ${styles.textarea}`}
              value={form.system_prompt}
              onChange={set("system_prompt")}
              placeholder="You are an experienced SDR writing a first-touch cold email. Identify the single most likely problem this prospect has right now, then open with it."
            />
          </div>

          <div className={styles.formGroup}>
            <label>Tone of voice</label>
            <select className={styles.input} value={form.tone_of_voice} onChange={set("tone_of_voice")}>
              {TONES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.formGroup}>
            <label>Who the email is from</label>
            <input
              className={styles.input}
              value={form.sender_role}
              onChange={set("sender_role")}
              placeholder="Founder at Acme, a deliverability tool for B2B sales teams"
            />
            <span className={styles.fieldHint}>
              Without this the AI invents a value proposition, which is the main cause of generic drafts.
            </span>
          </div>

          <div className={styles.formGroup}>
            <label>What you actually do for customers</label>
            <textarea
              className={`${styles.input} ${styles.textareaSm}`}
              value={form.value_proposition}
              onChange={set("value_proposition")}
              placeholder="We cut the time SDR teams spend building lists from about an hour a day to ten minutes."
            />
          </div>

          <div className={styles.formGroup}>
            <label>One concrete proof point</label>
            <input
              className={styles.input}
              value={form.proof_point}
              onChange={set("proof_point")}
              placeholder="Took Loop from a 4% to an 11% reply rate in six weeks"
            />
            <span className={styles.fieldHint}>Specific and checkable beats impressive-sounding.</span>
          </div>

          <div className={styles.formGroup}>
            <label>Call to action</label>
            <input
              className={styles.input}
              value={form.call_to_action}
              onChange={set("call_to_action")}
              placeholder="Ask if the problem is worth a short conversation. Do not ask for a meeting."
            />
          </div>

          <div className={styles.formGroup}>
            <label>Never mention</label>
            <input
              className={styles.input}
              value={form.avoid_topics}
              onChange={set("avoid_topics")}
              placeholder="pricing, competitors by name"
            />
          </div>

          <button className={styles.saveBtn} onClick={save} disabled={saving}>
            {saving ? <Loader2 size={18} className={styles.spin} /> : <Save size={18} />}
            {saving ? "Saving..." : "Save Prompt Settings"}
          </button>

          {notice && (
            <div className={notice.type === "error" ? styles.errorBox : styles.successBox}>
              {notice.type === "error" ? <AlertCircle size={16} /> : <Check size={16} />}
              <span>{notice.text}</span>
            </div>
          )}
        </div>

        {/* ---- Always-on rules (read only) ---- */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <ShieldCheck size={20} style={{ color: "var(--accent-success)" }} />
              Always Applied
              <span className={styles.lockTag}>
                <Lock size={11} /> not editable
              </span>
            </h2>
            <p className={styles.cardSubtitle}>{rules?.explanation}</p>
          </div>

          {rules?.sections?.map((section) => (
            <details key={section.title} className={styles.ruleBlock}>
              <summary className={styles.ruleSummary}>{section.title}</summary>
              <pre className={styles.rulePre}>{section.rules}</pre>
            </details>
          ))}
        </div>

        {/* ---- Spam tester ---- */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <Beaker size={20} className="text-accent-primary" />
              Spam Checker
            </h2>
            <p className={styles.cardSubtitle}>
              Paste any subject and body to score it before you send. Every generated draft is scored
              automatically with the same checks.
            </p>
          </div>

          <div className={styles.formGroup}>
            <label>Subject</label>
            <input
              className={styles.input}
              value={testSubject}
              onChange={(e) => setTestSubject(e.target.value)}
              placeholder="list building eating your mornings"
            />
          </div>

          <div className={styles.formGroup}>
            <label>Body</label>
            <textarea
              className={`${styles.input} ${styles.textarea}`}
              value={testBody}
              onChange={(e) => setTestBody(e.target.value)}
              placeholder="Paste an email body to score it."
            />
          </div>

          <button
            className={styles.secondaryBtn}
            onClick={runSpamCheck}
            disabled={testing || (!testSubject && !testBody)}
          >
            {testing ? <Loader2 size={16} className={styles.spin} /> : <Beaker size={16} />}
            {testing ? "Scoring..." : "Check for spam signals"}
          </button>

          {testResult && (
            <div className={styles.scoreBox}>
              <div className={styles.dualScore}>
                <div>
                  <span className={styles.scoreLabel}>Spam filter</span>
                  <div className={styles.scoreHead}>
                    <span className={styles.scoreNumber} style={{ color: gradeColor(testResult.grade) }}>
                      {testResult.score}
                      <small>/100</small>
                    </span>
                    <span className={styles.scoreGrade} style={{ color: gradeColor(testResult.grade) }}>
                      {testResult.grade}
                    </span>
                  </div>
                </div>
                {testResult.promotions && (
                  <div>
                    <span className={styles.scoreLabel}>Primary tab</span>
                    <div className={styles.scoreHead}>
                      <span
                        className={styles.scoreNumber}
                        style={{ color: gradeColor(testResult.promotions.grade) }}
                      >
                        {testResult.promotions.score}
                        <small>/100</small>
                      </span>
                      <span
                        className={styles.scoreGrade}
                        style={{ color: gradeColor(testResult.promotions.grade) }}
                      >
                        {testResult.promotions.grade}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {testResult.promotions?.issues?.length > 0 && (
                <>
                  <h4 className={styles.issueHeading}>Promotions tab risk</h4>
                  <ul className={styles.issueList}>
                    {testResult.promotions.issues.map((issue, i) => (
                      <li key={`p${i}`}>
                        <span className={styles.sevDot} style={{ background: SEVERITY_COLOR[issue.severity] }} />
                        <span>
                          <strong>{issue.field}</strong> &mdash; {issue.message}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {testResult.issues.length > 0 && <h4 className={styles.issueHeading}>Spam risk</h4>}

              {testResult.issues.length === 0 ? (
                <p className={styles.noIssues}>No spam signals found.</p>
              ) : (
                <ul className={styles.issueList}>
                  {testResult.issues.map((issue, i) => (
                    <li key={i}>
                      <span className={styles.sevDot} style={{ background: SEVERITY_COLOR[issue.severity] }} />
                      <span>
                        <strong>{issue.field}</strong> &mdash; {issue.message}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
      </div>
      <ABTestCard />
    </SettingsModule>
  );
}
