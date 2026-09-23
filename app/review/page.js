"use client";

import styles from "./page.module.css";
import { useState } from "react";
import { Check, X, Send, Sparkles, RefreshCw } from "lucide-react";

const QUEUE_DATA = [
  { 
    id: 1, 
    name: "Charlie Davis", 
    company: "Growthify", 
    icpScore: 78,
    intentSignals: ["💼 New CMO appointed"],
    researchSummary: "Growthify brought on a new CMO last month, likely restructuring their martech stack.",
    message: "Hi Charlie,\n\nI noticed Growthify is scaling its marketing efforts. Our AI outreach tool can help you automate your lead generation while keeping it highly personalized.\n\nWould you be open to a quick 10-minute chat this week?" 
  },
  { 
    id: 2, 
    name: "Evan Wright", 
    company: "Stripe", 
    icpScore: 88,
    intentSignals: ["🚀 New product launch"],
    researchSummary: "Expanding their billing products, ideal timing for sales tooling.",
    message: "Hey Evan,\n\nSaw your recent post about Stripe's expansion. We help fintech companies streamline their sales process with automated AI messaging.\n\nLet me know if you're interested in seeing a demo." 
  },
];

export default function ReviewPage() {
  const [activeItem, setActiveItem] = useState(QUEUE_DATA[0]);
  const [message, setMessage] = useState(activeItem?.message || "");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showSignals, setShowSignals] = useState(false);
  const [showResearch, setShowResearch] = useState(false);

  const handleSelect = (item) => {
    setActiveItem(item);
    setMessage(item.message);
    setShowSignals(false);
    setShowResearch(false);
  };

  const toggleSelect = (id, e) => {
    e.stopPropagation();
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) newSelected.delete(id);
    else newSelected.add(id);
    setSelectedIds(newSelected);
  };

  return (
    <div className={styles.page}>
      <div className={styles.queueList}>
        <div className={styles.listHeader} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Pending Reviews ({QUEUE_DATA.length})</span>
          {selectedIds.size > 0 && (
            <button className={styles.btnApprove} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
              Approve ({selectedIds.size})
            </button>
          )}
        </div>
        <div className={styles.listContent}>
          {QUEUE_DATA.map((item) => (
            <div 
              key={item.id} 
              className={`${styles.queueItem} ${activeItem?.id === item.id ? styles.active : ""}`}
              onClick={() => handleSelect(item)}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                <input 
                  type="checkbox" 
                  checked={selectedIds.has(item.id)}
                  onChange={(e) => toggleSelect(item.id, e)}
                  onClick={(e) => e.stopPropagation()}
                  style={{ marginTop: '0.25rem' }}
                />
                <div>
                  <div className={styles.leadName}>{item.name}</div>
                  <div className={styles.leadCompany}>{item.company}</div>
                </div>
              </div>
              <div className={styles.scoreBadge} style={{ 
                background: item.icpScore > 80 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                color: item.icpScore > 80 ? 'var(--accent-success)' : 'var(--accent-warning)',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 600
              }}>
                {item.icpScore}
              </div>
            </div>
          ))}
        </div>
      </div>

      {activeItem && (
        <div className={`${styles.reviewPanel} animate-fade-in`}>
          <div className={styles.panelHeader}>
            <div className={styles.leadInfo}>
              <h2>{activeItem.name}</h2>
              <p>{activeItem.company}</p>
            </div>
          </div>
          
          <div style={{ padding: '1.5rem 2rem 0' }}>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              {!showSignals ? (
                <button 
                  onClick={() => setShowSignals(true)}
                  style={{ background: 'var(--bg-surface-hover)', border: '1px solid var(--bg-border)', padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                  Show Detected Signals ({activeItem.intentSignals.length})
                </button>
              ) : (
                <div style={{ flex: '1 1 300px', padding: '1rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--bg-border)', position: 'relative' }}>
                  <button onClick={() => setShowSignals(false)} style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={14}/></button>
                  <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Detected Signals</h3>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {activeItem.intentSignals.map((sig, i) => (
                      <li key={i} style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{sig}</li>
                    ))}
                  </ul>
                </div>
              )}

              {!showResearch ? (
                <button 
                  onClick={() => setShowResearch(true)}
                  style={{ background: 'var(--bg-surface-hover)', border: '1px solid var(--bg-border)', padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--accent-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                  <Sparkles size={14} /> Show AI Research
                </button>
              ) : (
                <div style={{ flex: '1 1 300px', padding: '1rem', background: 'rgba(99, 102, 241, 0.05)', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.2)', position: 'relative' }}>
                  <button onClick={() => setShowResearch(false)} style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', opacity: 0.7 }}><X size={14}/></button>
                  <h3 style={{ fontSize: '0.875rem', color: 'var(--accent-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Sparkles size={16} /> AI Research
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                    {activeItem.researchSummary}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className={styles.messageEditor} style={{ marginTop: '0.5rem' }}>
            <label>Generated Message</label>
            <textarea 
              className={styles.textarea}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>

          <div className={styles.actions}>
            <button className={`${styles.btn} ${styles.btnReject}`}>
              <X size={18} />
              Reject
            </button>
            <button className={`${styles.btn} ${styles.btnRegenerate}`} style={{ background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', color: 'var(--text-primary)' }}>
              <RefreshCw size={18} />
              Regenerate
            </button>
            <button className={`${styles.btn} ${styles.btnApprove}`}>
              <Send size={18} />
              Approve & Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
