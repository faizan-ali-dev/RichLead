"use client";

import { API_BASE } from "../lib/api";
import LlmProviderCard from "./LlmProviderCard";
import BusinessInfoCard from "./BusinessInfoCard";
import FollowUpCard from "./FollowUpCard";

import styles from "./page.module.css";
import { Key, Save, User, Webhook, Cpu, Zap, Bot } from "lucide-react";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import useAutopilotSetting from "@/components/useAutopilotSetting";

export default function SettingsPage() {
  const router = useRouter();
  const { autopilot, updateAutopilot, isSaving: isSavingAutopilot, error: autopilotError } = useAutopilotSetting();
  const [apiKeys, setApiKeys] = useState({ apollo: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");

  const fetchKeys = async (accessToken) => {
    try {
      // Fetch API Keys
      const res = await fetch(`${API_BASE}/api/integrations/api-keys/`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        // Since we are mocking we just ensure it doesn't crash
      }
    } catch (err) {}
  };

  useEffect(() => {
    const storedToken = localStorage.getItem("richlead_token");
    if (storedToken) {
      fetchKeys(storedToken);
    } else {
      router.replace("/login");
    }
  }, [router]);

  const handleKeyChange = (prov, val) => {
    setApiKeys(prev => ({ ...prev, [prov]: val }));
  };

  const handleSave = async () => {
    const token = localStorage.getItem("richlead_token");
    if (!token) return;
    setIsSaving(true);
    setSaveStatus("");
    try {
      // Save Apollo key if provided
      if (apiKeys.apollo) {
        await fetch(`${API_BASE}/api/integrations/api-keys/`, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}` 
          },
          body: JSON.stringify({ provider: "apollo", api_key: apiKeys.apollo })
        });
      }
      
      setSaveStatus("Settings saved successfully!");
      // clear the inputs for security
      setApiKeys({ apollo: "" });
    } catch (err) {
      setSaveStatus("Failed to save settings.");
    }
    setIsSaving(false);
  };

  return (
    <div className={`${styles.page} animate-fade-in`}>
      <div className={styles.section}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <h2 className={styles.sectionTitle} style={{marginBottom: 0}}>
            <Zap size={20} className="text-accent-primary" />
            Autopilot Configuration
          </h2>
          <label className="toggle-switch" style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: isSavingAutopilot ? 'wait' : 'pointer' }}>
            <span style={{ fontWeight: 500, color: autopilot ? 'var(--accent-success)' : 'var(--text-secondary)' }}>
              {isSavingAutopilot ? "Saving…" : autopilot ? "Active" : "Paused"}
            </span>
            <input type="checkbox" checked={autopilot} disabled={isSavingAutopilot} onChange={(event) => updateAutopilot(event.target.checked)} aria-label="Enable Autopilot" />
          </label>
        </div>
        {autopilotError && <p role="alert" style={{ color: 'var(--accent-danger)', fontSize: '0.875rem', marginTop: '0.75rem' }}>{autopilotError}</p>}
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '1rem' }}>
          When active, the system will automatically generate and send emails to leads without manual review.
        </p>
      </div>

      <BusinessInfoCard />

      <LlmProviderCard />

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <Bot size={20} className="text-accent-primary" />
          Prompt Engineering
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Configure system prompts, tone of voice, and custom instructions for the AI outreach generator.
          These are sent to whichever AI provider is active above.
        </p>
        <Link href="/settings/prompts" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--bg-surface-hover)', border: '1px solid var(--bg-border)', padding: '0.6rem 1.25rem', borderRadius: '8px', color: 'var(--text-primary)', fontWeight: 500, textDecoration: 'none' }}>
          <Bot size={18} className="text-accent-primary" />
          Manage LLM Prompts
        </Link>
      </div>

      <FollowUpCard />

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <User size={20} className="text-accent-primary" />
          Profile Settings
        </h2>
        
        <div className={styles.formGroup}>
          <label>Full Name</label>
          <input type="text" className={styles.input} defaultValue="Admin User" />
        </div>
        
        <div className={styles.formGroup}>
          <label>Email Address</label>
          <input type="email" className={styles.input} defaultValue="admin@richlead.com" />
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <Webhook size={20} className="text-accent-primary" />
          CRM Integrations (Webhooks)
        </h2>

        <div className={styles.formGroup}>
          <label>Positive Reply Webhook URL (e.g. Zapier, HubSpot)</label>
          <input type="url" className={styles.input} placeholder="https://hooks.zapier.com/hooks/catch/..." />
        </div>
        
        <div className={styles.formGroup}>
          <label>Meeting Booked Webhook URL</label>
          <input type="url" className={styles.input} placeholder="https://..." />
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <Key size={20} className="text-accent-primary" />
          Other Integrations
        </h2>

        <div className={styles.formGroup}>
          <label>Apollo API Key</label>
          <input type="password" className={styles.input} placeholder="••••••••••••••••" value={apiKeys.apollo} onChange={e => handleKeyChange('apollo', e.target.value)} />
        </div>

        <button className={styles.saveBtn} onClick={handleSave} disabled={isSaving}>
          <Save size={18} />
          {isSaving ? "Saving..." : "Save All Settings"}
        </button>
        {saveStatus && (
          <p style={{ marginTop: '1rem', color: saveStatus.includes('success') ? 'var(--accent-success)' : 'var(--accent-danger)', fontSize: '0.875rem' }}>
            {saveStatus}
          </p>
        )}
      </div>
    </div>
  );
}
