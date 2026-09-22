"use client";

import styles from "./page.module.css";
import { useState } from "react";
import { Check, X, Send } from "lucide-react";

const QUEUE_DATA = [
  { 
    id: 1, 
    name: "Charlie Davis", 
    company: "Growthify", 
    message: "Hi Charlie,\n\nI noticed Growthify is scaling its marketing efforts. Our AI outreach tool can help you automate your lead generation while keeping it highly personalized.\n\nWould you be open to a quick 10-minute chat this week?" 
  },
  { 
    id: 2, 
    name: "Evan Wright", 
    company: "Stripe", 
    message: "Hey Evan,\n\nSaw your recent post about Stripe's expansion. We help fintech companies streamline their sales process with automated AI messaging.\n\nLet me know if you're interested in seeing a demo." 
  },
];

export default function ReviewPage() {
  const [activeItem, setActiveItem] = useState(QUEUE_DATA[0]);
  const [message, setMessage] = useState(activeItem?.message || "");

  const handleSelect = (item) => {
    setActiveItem(item);
    setMessage(item.message);
  };

  return (
    <div className={styles.page}>
      <div className={styles.queueList}>
        <div className={styles.listHeader}>
          Pending Reviews ({QUEUE_DATA.length})
        </div>
        <div className={styles.listContent}>
          {QUEUE_DATA.map((item) => (
            <div 
              key={item.id} 
              className={`${styles.queueItem} ${activeItem?.id === item.id ? styles.active : ""}`}
              onClick={() => handleSelect(item)}
            >
              <div className={styles.leadName}>{item.name}</div>
              <div className={styles.leadCompany}>{item.company}</div>
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
          
          <div className={styles.messageEditor}>
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
