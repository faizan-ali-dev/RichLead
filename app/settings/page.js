"use client";

import styles from "./page.module.css";
import { Key, Save, User, Webhook, Cpu, Zap, Bot } from "lucide-react";
import { useState, useEffect } from "react";
import Link from "next/link";

export default function SettingsPage() {
  const [provider, setProvider] = useState("openai");
  const [autopilot, setAutopilot] = useState(false);
  const [apiKeys, setApiKeys] = useState({
    openai: "",
    claude: "",
    groq: "",
    apollo: ""
  });
  const [token, setToken] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");

  useEffect(() => {
    const storedToken = localStorage.getItem("richlead_token");
    if (storedToken) {
      setToken(storedToken);
      fetchKeys(storedToken);
    } else {
      window.location.href = "/login";
    }
  }, []);

  const fetchKeys = async (accessToken) => {
    try {
      // Fetch user settings (including autopilot)
      const userRes = await fetch("http://127.0.0.1:8000/api/users/settings/", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (userRes.ok) {
        const userData = await userRes.json();
        setAutopilot(userData.autopilot_active || false);
      } else if (userRes.status === 401) {
        localStorage.removeItem("richlead_token");
        window.location.href = "/login";
        return;
      }

      // Fetch API Keys
      const res = await fetch("http://127.0.0.1:8000/api/integrations/api-keys/", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        // Since we are mocking we just ensure it doesn't crash
      }
    } catch (err) {}
  };

  const handleKeyChange = (prov, val) => {
    setApiKeys(prev => ({ ...prev, [prov]: val }));
  };

  const handleSave = async () => {
    if (!token) return;
    setIsSaving(true);
    setSaveStatus("");
    try {
      // Save User Settings (Autopilot)
      await fetch("http://127.0.0.1:8000/api/users/settings/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
        },
        body: JSON.stringify({ autopilot_active: autopilot })
      });

      // Save the active LLM provider key
      if (apiKeys[provider]) {
        await fetch("http://127.0.0.1:8000/api/integrations/api-keys/", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}` 
          },
          body: JSON.stringify({ provider, api_key: apiKeys[provider] })
        });
      }
      
      // Save Apollo key if provided
      if (apiKeys.apollo) {
        await fetch("http://127.0.0.1:8000/api/integrations/api-keys/", {
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
      setApiKeys({ openai: "", claude: "", groq: "", apollo: "" });
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
          <label className="toggle-switch" style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
            <span style={{ fontWeight: 500, color: autopilot ? 'var(--accent-success)' : 'var(--text-secondary)' }}>
              {autopilot ? "Active" : "Paused"}
            </span>
            <div style={{ position: 'relative', width: '44px', height: '24px', backgroundColor: autopilot ? 'var(--accent-success)' : 'var(--bg-border)', borderRadius: '34px', transition: '0.4s' }} onClick={() => setAutopilot(!autopilot)}>
              <div style={{ position: 'absolute', top: '3px', left: autopilot ? '23px' : '3px', width: '18px', height: '18px', backgroundColor: 'white', borderRadius: '50%', transition: '0.4s' }}></div>
            </div>
          </label>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '1rem' }}>
          When active, the system will automatically generate and send emails to leads without manual review.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <Cpu size={20} className="text-accent-primary" />
          AI & LLM Provider
        </h2>
        
        <div className={styles.formGroup}>
          <label>Active LLM Provider</label>
          <select className={styles.input} value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="openai">OpenAI (GPT-4)</option>
            <option value="claude">Anthropic (Claude 3.5 Sonnet)</option>
            <option value="groq">Groq (Llama 3)</option>
          </select>
        </div>

        {provider === "openai" && (
          <div className={styles.formGroup}>
            <label>OpenAI API Key</label>
            <input type="password" className={styles.input} placeholder="sk-proj-..." value={apiKeys.openai} onChange={e => handleKeyChange('openai', e.target.value)} />
          </div>
        )}

        {provider === "claude" && (
          <div className={styles.formGroup}>
            <label>Anthropic API Key</label>
            <input type="password" className={styles.input} placeholder="sk-ant-..." value={apiKeys.claude} onChange={e => handleKeyChange('claude', e.target.value)} />
          </div>
        )}

        {provider === "groq" && (
          <div className={styles.formGroup}>
            <label>Groq API Key</label>
            <input type="password" className={styles.input} placeholder="gsk_..." value={apiKeys.groq} onChange={e => handleKeyChange('groq', e.target.value)} />
          </div>
        )}

        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--bg-border)' }}>
          <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Prompt Engineering</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Configure system prompts, tone of voice, and custom instructions for the AI outreach generator.
          </p>
          <Link href="/settings/prompts" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--bg-surface-hover)', border: '1px solid var(--bg-border)', padding: '0.6rem 1.25rem', borderRadius: '8px', color: 'var(--text-primary)', fontWeight: 500, textDecoration: 'none', transition: 'background-color 0.2s' }}>
            <Bot size={18} className="text-accent-primary" />
            Manage LLM Prompts
          </Link>
        </div>
      </div>

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

        <button className={styles.saveBtn} onClick={handleSave} disabled={isSaving || !token}>
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
