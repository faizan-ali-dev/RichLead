"use client";

import styles from "./page.module.css";
import { Plus, Save } from "lucide-react";
import { useState } from "react";

export default function SequencesPage() {
  const [steps, setSteps] = useState([
    {
      id: 1,
      title: "Initial Outreach",
      delay: "Immediate",
      prompt: "You are an expert sales rep. Write a highly personalized intro message focusing on recent company growth."
    },
    {
      id: 2,
      title: "Follow-up 1 (Value Add)",
      delay: "Wait 3 days",
      prompt: "Reply to the previous thread. Keep it short. Provide one specific piece of value or a case study related to their niche."
    },
    {
      id: 3,
      title: "Follow-up 2 (Breakup)",
      delay: "Wait 7 days",
      prompt: "This is the final breakup email. Be polite, ask if now is just a bad time, and leave the door open for future contact."
    }
  ]);

  const addStep = () => {
    setSteps([...steps, {
      id: steps.length + 1,
      title: `Follow-up ${steps.length}`,
      delay: "Wait 5 days",
      prompt: "New AI prompt instructions..."
    }]);
  };

  return (
    <div className={styles.page}>
      <div className={styles.controls}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Multi-step Sequences</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Define how the AI should follow up with leads who don't reply.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className={styles.addBtn} onClick={addStep} style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--bg-border)', color: 'var(--text-primary)' }}>
            <Plus size={18} />
            Add Step
          </button>
          <button className={styles.addBtn}>
            <Save size={18} />
            Save Sequence
          </button>
        </div>
      </div>

      <div className={styles.sequenceContainer}>
        {steps.map((step) => (
          <div key={step.id} className={`${styles.stepCard} animate-fade-in`}>
            <div className={styles.stepHeader}>
              <div className={styles.stepNumber}>{step.id}</div>
              <div className={styles.stepTitle}>{step.title}</div>
              <div className={styles.stepDelay}>{step.delay}</div>
            </div>
            
            <textarea 
              className={styles.promptArea} 
              defaultValue={step.prompt}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
