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

    </div>
  );
}
