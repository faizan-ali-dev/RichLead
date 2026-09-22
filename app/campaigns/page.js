"use client";

import styles from "./page.module.css";
import { Target, Bot, Save, Mail, MessageCircle } from "lucide-react";
import { useState } from "react";

export default function CampaignsPage() {
  const [channel, setChannel] = useState("email");

  return (
    <div className={styles.page}>
      <div className={`${styles.column} animate-fade-in`}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <Target size={20} className="text-accent-primary" />
              Apollo Search Targeting
            </h2>
          </div>
          
          <div className={styles.formGroup}>
            <label>Target Niche / Industry</label>
            <input type="text" className={styles.input} defaultValue="B2B SaaS, Fintech" />
          </div>
          
          <div className={styles.formGroup}>
            <label>Job Titles</label>
            <input type="text" className={styles.input} defaultValue="Founder, CEO, VP of Sales" />
          </div>

          <div className={styles.formGroup}>
            <label>Location</label>
            <input type="text" className={styles.input} defaultValue="United States, United Kingdom" />
          </div>

          <div className={styles.formGroup}>
            <label>Company Headcount</label>
            <input type="text" className={styles.input} defaultValue="11-50, 51-200" />
          </div>

          <div className={styles.formGroup}>
            <label>Leads to Fetch (Bulk Limit)</label>
            <input type="number" className={styles.input} defaultValue="1000" />
          </div>

          <div className={styles.actionGroup}>
            <button className={styles.saveBtn}>
              <Save size={18} />
              Save Targeting
            </button>
            <button className={styles.fetchBtn}>
              <Target size={18} />
              Fetch Leads Now
            </button>
          </div>
        </div>
      </div>

      <div className={`${styles.column} animate-fade-in`} style={{ animationDelay: "0.1s" }}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <Bot size={20} className="text-accent-primary" />
              LLM Prompt Settings
            </h2>
          </div>

          <div className={styles.formGroup}>
            <label>Outreach Channel</label>
            <div className={styles.channelToggle}>
              <div 
                className={`${styles.channelOption} ${channel === "email" ? styles.active : ""}`}
                onClick={() => setChannel("email")}
              >
                <Mail size={18} /> Email
              </div>
              <div 
                className={`${styles.channelOption} ${channel === "sms" ? styles.active : ""}`}
                onClick={() => setChannel("sms")}
              >
                <MessageCircle size={18} /> SMS
              </div>
            </div>
          </div>

          <div className={styles.formGroup}>
            <label>System Prompt (Instructions)</label>
            <textarea 
              className={`${styles.input} ${styles.textarea}`} 
              defaultValue="You are an expert sales development rep. Write a concise, personalized outreach message to the provided lead. Focus on their company's recent growth and offer a brief solution."
            />
          </div>

          <div className={styles.formGroup}>
            <label>Tone of Voice</label>
            <select className={styles.input} defaultValue="professional">
              <option value="professional">Professional & Direct</option>
              <option value="casual">Friendly & Casual</option>
              <option value="humorous">Humorous</option>
            </select>
          </div>

          <button className={styles.saveBtn}>
            <Save size={18} />
            Save Prompt
          </button>
        </div>
      </div>
    </div>
  );
}
