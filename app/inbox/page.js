"use client";

import styles from "./page.module.css";
import { Mail, Send, Sparkles, MoreVertical, PanelLeft } from "lucide-react";
import { useState } from "react";

const MESSAGES = [
  { id: 1, name: "Sarah Jenkins", subject: "Re: Quick question about your sales process", time: "10:42 AM", preview: "Hi Faizan, thanks for reaching out. Yes, we are currently looking into..." },
  { id: 2, name: "David Chen", subject: "Re: Scaling your outreach", time: "Yesterday", preview: "Can we schedule a quick call next week to discuss this further?" },
  { id: 3, name: "Michael Ross", subject: "Not interested", time: "Yesterday", preview: "Please remove me from your mailing list." },
  { id: 4, name: "Emily Watson", subject: "Re: Your tech stack", time: "Oct 18", preview: "Who is the right person to speak with regarding this?" },
];

export default function InboxPage() {
  const [activeMsg, setActiveMsg] = useState(MESSAGES[0]);
  const [showSidebar, setShowSidebar] = useState(true);

  return (
    <div className={styles.page}>
      {showSidebar && (
        <div className={`${styles.sidebar} animate-fade-in`}>
        <div className={styles.sidebarHeader}>
          Unified Inbox
        </div>
        <div className={styles.messageList}>
          {MESSAGES.map((msg) => (
            <div 
              key={msg.id} 
              className={`${styles.messageItem} ${activeMsg.id === msg.id ? styles.active : ""}`}
              onClick={() => setActiveMsg(msg)}
            >
              <div className={styles.msgName}>
                {msg.name}
                <span className={styles.msgTime}>{msg.time}</span>
              </div>
              <div className={styles.msgSubject}>{msg.subject}</div>
              <div className={styles.msgPreview}>{msg.preview}</div>
            </div>
          ))}
        </div>
        </div>
      )}

      <div className={`${styles.mainView} animate-fade-in`} style={{ animationDelay: '0.1s' }}>
        <div className={styles.threadHeader}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button 
                onClick={() => setShowSidebar(!showSidebar)}
                style={{ background: 'var(--bg-surface-hover)', border: '1px solid var(--bg-border)', cursor: 'pointer', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', padding: '0.4rem', borderRadius: '6px' }}
                title="Toggle Sidebar"
              >
                <PanelLeft size={18} />
              </button>
              <h2 className={styles.threadSubject} style={{ margin: 0 }}>{activeMsg.subject}</h2>
            </div>
            <button style={{ color: 'var(--text-secondary)', cursor: 'pointer', background: 'none', border: 'none' }}>
              <MoreVertical size={20} />
            </button>
          </div>
          <div className={styles.threadInfo}>
            <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{activeMsg.name}</span>
            <span>&lt;{activeMsg.name.toLowerCase().replace(' ', '.')}@example.com&gt;</span>
            <span style={{ marginLeft: 'auto' }}>{activeMsg.time}</span>
          </div>
        </div>

        <div className={styles.threadBody}>
          <p style={{ marginBottom: '1rem' }}>Hi Faizan,</p>
          <p style={{ marginBottom: '1rem' }}>
            Thanks for reaching out. Yes, we are currently looking into ways to automate our outbound process. 
            Your solution sounds interesting. 
          </p>
          <p style={{ marginBottom: '1rem' }}>Do you have some time for a quick 15-minute demo on Thursday?</p>
          <p>Best regards,<br/>{activeMsg.name}</p>
          
          <hr style={{ margin: '2rem 0', borderColor: 'var(--bg-border)' }} />
          
          <div style={{ color: 'var(--text-muted)' }}>
            <p>On {activeMsg.time}, you wrote:</p>
            <p style={{ borderLeft: '3px solid var(--bg-border)', paddingLeft: '1rem', marginTop: '0.5rem' }}>
              Hey {activeMsg.name.split(' ')[0]}, noticed your recent growth. I have a solution that automates this entire process...
            </p>
          </div>
        </div>

        <div className={styles.replyBox}>
          <textarea 
            className={styles.textarea} 
            placeholder="Type your reply here..."
          ></textarea>
          <div className={styles.replyActions}>
            <button className={styles.aiBtn}>
              <Sparkles size={16} />
              Draft AI Reply
            </button>
            <button className={styles.sendBtn}>
              <Send size={16} />
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
