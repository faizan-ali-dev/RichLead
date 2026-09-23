"use client";

import styles from "./page.module.css";
import { Key, Save, User, Webhook, Cpu, Zap, Bot } from "lucide-react";
import { useState } from "react";
import Link from "next/link";

export default function SettingsPage() {
  const [provider, setProvider] = useState("openai");
  const [autopilot, setAutopilot] = useState(false);

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
            <input type="password" className={styles.input} defaultValue="sk-proj-••••••••••••••••" />
          </div>
        )}

        {provider === "claude" && (
          <div className={styles.formGroup}>
            <label>Anthropic API Key</label>
            <input type="password" className={styles.input} placeholder="sk-ant-••••••••••••••••" />
          </div>
        )}

        {provider === "groq" && (
          <div className={styles.formGroup}>
            <label>Groq API Key</label>
            <input type="password" className={styles.input} placeholder="gsk_••••••••••••••••" />
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
          <input type="password" className={styles.input} defaultValue="••••••••••••••••" />
        </div>

        <button className={styles.saveBtn}>
          <Save size={18} />
          Save All Settings
        </button>
      </div>
    </div>
  );
}
