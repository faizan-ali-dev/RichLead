"use client";

import { useEffect, useState } from "react";
import { Check, KeyRound, Save } from "lucide-react";
import SettingsModule from "@/components/SettingsModule";
import { authFetch } from "@/app/lib/api";
import styles from "../page.module.css";

const PROVIDERS = [
  {
    id: "apollo",
    name: "Apollo",
    description: "Search people, companies, and saved contacts. Apollo endpoint access and email enrichment may depend on your plan; enrichment can use credits.",
  },
  {
    id: "hunter",
    name: "Hunter",
    description: "Discover company previews for free, or import only valid personal work emails for a company/domain. Contact searches can consume Hunter credits.",
  },
];

export default function IntegrationSettingsPage() {
  const [apiKeys, setApiKeys] = useState({ apollo: "", hunter: "" });
  const [connected, setConnected] = useState({ apollo: false, hunter: false });
  const [isLoading, setIsLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState("");
  const [notices, setNotices] = useState({ apollo: "", hunter: "" });

  useEffect(() => {
    let active = true;
    authFetch("/api/integrations/api-keys/")
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load connected APIs.");
        const payload = await response.json();
        const integrations = Array.isArray(payload) ? payload : payload.results || [];
        if (active) {
          setConnected({
            apollo: integrations.some((item) => item.provider === "apollo" && item.is_active),
            hunter: integrations.some((item) => item.provider === "hunter" && item.is_active),
          });
        }
      })
      .catch((error) => {
        if (active) setNotices({ apollo: error.message, hunter: error.message });
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, []);

  const setKey = (provider, value) => setApiKeys((current) => ({ ...current, [provider]: value }));

  const save = async (event, provider) => {
    event.preventDefault();
    const key = apiKeys[provider].trim();
    if (!key) return;
    setSavingProvider(provider);
    setNotices((current) => ({ ...current, [provider]: "" }));
    try {
      const response = await authFetch("/api/integrations/api-keys/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: key }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.api_key?.[0] || data.detail || "Could not save the API key.";
        throw new Error(Array.isArray(detail) ? detail.join(" ") : detail);
      }
      setKey(provider, "");
      setConnected((current) => ({ ...current, [provider]: true }));
      setNotices((current) => ({ ...current, [provider]: `${provider === "hunter" ? "Hunter" : "Apollo"} API key saved securely${provider === "hunter" ? " and verified" : ""}.` }));
    } catch (error) {
      setNotices((current) => ({ ...current, [provider]: error.message || "Could not save the API key." }));
    } finally {
      setSavingProvider("");
    }
  };

  return (
    <SettingsModule title="API integrations" description="Connect external data providers used to find and enrich leads.">
      {PROVIDERS.map((provider) => (
        <section className={styles.section} key={provider.id}>
          <h3 className={styles.sectionTitle}><KeyRound size={20} className="text-accent-primary" /> {provider.name}</h3>
          <p className={styles.hint}>{provider.description}</p>
          {isLoading ? <p className={styles.hint}>Checking connection…</p> : (
            <p className={styles.hint}>
              {connected[provider.id] ? <><Check size={15} /> {provider.name} is connected. Its secret key is hidden.</> : `${provider.name} is not connected yet.`}
            </p>
          )}
          <form onSubmit={(event) => save(event, provider.id)}>
            <div className={styles.formGroup}>
              <label htmlFor={`${provider.id}-api-key`}>{provider.name} API key</label>
              <input
                id={`${provider.id}-api-key`}
                type="password"
                autoComplete="new-password"
                className={styles.input}
                placeholder={connected[provider.id] ? "Enter a new key to replace the saved one" : `Paste your ${provider.name} API key`}
                value={apiKeys[provider.id]}
                onChange={(event) => setKey(provider.id, event.target.value)}
              />
            </div>
            <button className={styles.saveBtn} type="submit" disabled={savingProvider === provider.id || !apiKeys[provider.id].trim()}>
              <Save size={18} /> {savingProvider === provider.id ? "Saving…" : `Save ${provider.name} key`}
            </button>
          </form>
          {notices[provider.id] && <p role="status" className={notices[provider.id].includes("saved") ? styles.successBox : styles.errorBox}>{notices[provider.id]}</p>}
        </section>
      ))}
    </SettingsModule>
  );
}
