"use client";

import styles from "./page.module.css";
import { Bot, Save, Mail, MessageCircle, ArrowLeft } from "lucide-react";
import { useState } from "react";
import Link from "next/link";

export default function PromptsSettingsPage() {
  const [channel, setChannel] = useState("email");

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Link href="/settings" className={styles.backBtn}>
          <ArrowLeft size={18} />
          Back to Settings
        </Link>
      </div>
      <div className={`${styles.column} animate-fade-in`}>
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
