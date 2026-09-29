"use client";

import { useEffect, useState } from "react";
import { Check, KeyRound, Save } from "lucide-react";
import SettingsModule from "@/components/SettingsModule";
import { authFetch } from "@/app/lib/api";
import styles from "../page.module.css";

export default function IntegrationSettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [isConfigured, setIsConfigured] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    authFetch("/api/integrations/api-keys/")
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load connected APIs.");
        const payload = await response.json();
        const integrations = Array.isArray(payload) ? payload : payload.results || [];
        if (active) setIsConfigured(integrations.some((item) => item.provider === "apollo" && item.is_active));
      })
      .catch((error) => {
        if (active) setNotice(error.message || "Could not load connected APIs.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, []);

  const save = async (event) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setIsSaving(true);
    setNotice("");
    try {
      const response = await authFetch("/api/integrations/api-keys/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "apollo", api_key: apiKey.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.api_key?.[0] || "Could not save the Apollo key.");
      setApiKey("");
      setIsConfigured(true);
      setNotice("Apollo API key saved securely.");
    } catch (error) {
      setNotice(error.message || "Could not save the Apollo key.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <SettingsModule title="API integrations" description="Connect external data providers used to find and enrich leads.">
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}><KeyRound size={20} className="text-accent-primary" /> Apollo</h3>
        <p className={styles.hint}>
          Prospecting filters for Apollo-verified emails and imports only verified work addresses. Email enrichment can use Apollo credits; phone enrichment is disabled, and searches are capped at 10 leads while testing.
        </p>
        {isLoading ? <p className={styles.hint}>Checking connection…</p> : (
          <p className={styles.hint}>
            {isConfigured ? <><Check size={15} /> Apollo is connected. Its secret key is hidden.</> : "Apollo is not connected yet."}
          </p>
        )}
        <form onSubmit={save}>
          <div className={styles.formGroup}>
            <label htmlFor="apollo-api-key">Apollo API key</label>
            <input
              id="apollo-api-key"
              type="password"
              autoComplete="new-password"
              className={styles.input}
              placeholder={isConfigured ? "Enter a new key to replace the saved one" : "Paste your Apollo API key"}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </div>
          <button className={styles.saveBtn} type="submit" disabled={isSaving || !apiKey.trim()}>
            <Save size={18} /> {isSaving ? "Saving…" : "Save Apollo key"}
          </button>
        </form>
        {notice && <p role="status" className={notice.includes("saved") ? styles.successBox : styles.errorBox}>{notice}</p>}
      </section>
    </SettingsModule>
  );
}
