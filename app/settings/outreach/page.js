"use client";

import { useEffect, useState } from "react";
import { Languages, Save } from "lucide-react";
import SettingsModule from "@/components/SettingsModule";
import { authFetch } from "@/app/lib/api";
import styles from "../page.module.css";

export default function ReachoutLanguagePage() {
  const [language, setLanguage] = useState("en");
  const [choices, setChoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    let active = true;
    authFetch("/api/users/settings/")
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load reachout language settings.");
        const data = await response.json();
        if (active) {
          setLanguage(data.reachout_language || "en");
          setChoices(data.reachout_language_choices || []);
        }
      })
      .catch((error) => {
        if (active) setNotice({ type: "error", text: error.message || "Could not load settings." });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const response = await authFetch("/api/users/settings/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reachout_language: language }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not save reachout language.");
      setNotice({ type: "success", text: "Reachout language saved. New AI drafts will use it." });
    } catch (error) {
      setNotice({ type: "error", text: error.message || "Network error while saving." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsModule
      title="Reachout language"
      description="Choose the language used for AI-generated outreach subjects and message drafts."
    >
      <section className={styles.section}>
        {loading ? <p className={styles.hint}>Loading language settings…</p> : (
          <>
            <div className={styles.formGroup}>
              <label htmlFor="reachout-language">
                <Languages size={16} aria-hidden="true" /> Reachout language
              </label>
              <select
                id="reachout-language"
                className={styles.input}
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
              >
                {choices.map((choice) => (
                  <option key={choice.value} value={choice.value}>{choice.label}</option>
                ))}
              </select>
            </div>
            <p className={styles.hint}>
              This applies to new AI drafts, including drafts created while prospecting. Existing drafts stay unchanged.
            </p>
            <button className={styles.saveBtn} onClick={save} disabled={saving}>
              <Save size={16} /> {saving ? "Saving…" : "Save language"}
            </button>
          </>
        )}
        {notice && (
          <p role={notice.type === "error" ? "alert" : "status"}
            className={notice.type === "error" ? styles.errorBox : styles.successBox}>
            {notice.text}
          </p>
        )}
      </section>
    </SettingsModule>
  );
}
