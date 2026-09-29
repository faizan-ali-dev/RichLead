"use client";

import { asList, authFetch, getAccessToken, redirectToLogin } from "../lib/api";

import styles from "./page.module.css";
import { Mail, Send, Sparkles, MoreVertical, PanelLeft, RefreshCw } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";

export default function InboxPage() {
  const [threads, setThreads] = useState([]);
  const [activeThread, setActiveThread] = useState(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [isSendingReply, setIsSendingReply] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const syncInFlight = useRef(false);

  const fetchInbox = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const response = await authFetch("/api/inbox/");
      if (response.ok) {
        const data = asList(await response.json());
        setThreads(data);
        setActiveThread((current) => {
          if (!data.length) return null;
          return data.find((thread) => thread.lead_id === current?.lead_id) || data[0];
        });
      }
    } catch (err) {
      console.error("Failed to fetch inbox", err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const triggerSync = useCallback(async (authToken) => {
    const t = authToken || getAccessToken();
    if (!t || syncInFlight.current) return;
    syncInFlight.current = true;
    setIsSyncing(true);
    try {
      const response = await authFetch("/api/inbox/sync/", {
        method: "POST",
      });
      if (response.ok) {
        await fetchInbox(true);
        setLastSyncedAt(new Date());
      }
    } catch (err) {
      console.error("Sync failed", err);
    } finally {
      syncInFlight.current = false;
      setIsSyncing(false);
    }
  }, [fetchInbox]);

  useEffect(() => {
    const storedToken = getAccessToken();
    if (!storedToken) {
      redirectToLogin();
      return undefined;
    }

    const initialLoad = window.setTimeout(() => {
      fetchInbox();
      triggerSync(storedToken);
    }, 0);
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") triggerSync(storedToken);
    }, 60_000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(interval);
    };
  }, [fetchInbox, triggerSync]);

  const handleSync = () => triggerSync(getAccessToken());

  const handleSendReply = async () => {
    if (!replyText.trim() || !activeThread) return;
    setIsSendingReply(true);
    
    try {
      const response = await authFetch("/api/integrations/send-email/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          lead_id: activeThread.lead_id,
          message: replyText
        })
      });
      
      const data = await response.json();
      if (response.ok && data.success) {
        alert("Reply sent successfully!");
        setReplyText("");
        // Reload inbox to show the sent message
        fetchInbox();
      } else {
        alert("Failed to send reply: " + (data.error || "Unknown error"));
      }
    } catch (err) {
      alert("Network error sending reply.");
    } finally {
      setIsSendingReply(false);
    }
  };

  const formatDate = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  };

  return (
    <div className={styles.page}>
      {showSidebar && (
        <div className={`${styles.sidebar} animate-fade-in`}>
        <div className={styles.sidebarHeader} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>
            Unified Inbox
            <span style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.7rem', fontWeight: 400, color: 'var(--text-muted)' }}>
              {isSyncing ? "Syncing mailboxes…" : lastSyncedAt ? `Auto-sync on · last sync ${lastSyncedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : "Auto-sync on · every minute"}
            </span>
          </span>
          <button 
            onClick={handleSync}
            disabled={isSyncing}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: isSyncing ? 'not-allowed' : 'pointer', opacity: isSyncing ? 0.5 : 1 }}
            title="Sync email now · automatic sync runs every minute while this page is open"
            aria-label="Sync email now"
          >
            <RefreshCw size={16} className={isSyncing ? "animate-spin" : ""} />
          </button>
        </div>
        <div className={styles.messageList}>
          {loading ? (
             <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading emails...</div>
          ) : threads.length === 0 ? (
             <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No emails found for approached leads.</div>
          ) : threads.map((thread) => {
            const latestMsg = thread.messages[0] || {};
            return (
              <div 
                key={thread.lead_id} 
                className={`${styles.messageItem} ${activeThread?.lead_id === thread.lead_id ? styles.active : ""}`}
                onClick={() => setActiveThread(thread)}
              >
                <div className={styles.msgName}>
                  {thread.lead_name}
                  <span className={styles.msgTime}>{latestMsg.received_at ? formatDate(latestMsg.received_at) : ''}</span>
                </div>
                <div className={styles.msgSubject}>{latestMsg.subject || 'No Subject'}</div>
                <div className={styles.msgPreview}>{latestMsg.body_text?.substring(0, 50) || '...'}</div>
              </div>
            );
          })}
        </div>
        </div>
      )}

      <div className={`${styles.mainView} animate-fade-in`} style={{ animationDelay: '0.1s' }}>
        {!activeThread ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
            Select a thread to view messages
          </div>
        ) : (
          <>
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
                  <h2 className={styles.threadSubject} style={{ margin: 0 }}>{activeThread.messages[0]?.subject || 'Email Thread'}</h2>
                </div>
                <button style={{ color: 'var(--text-secondary)', cursor: 'pointer', background: 'none', border: 'none' }}>
                  <MoreVertical size={20} />
                </button>
              </div>
              <div className={styles.threadInfo}>
                <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{activeThread.lead_name}</span>
                <span>&lt;{activeThread.lead_email}&gt;</span>
              </div>
            </div>

            <div className={styles.threadBody} style={{ overflowY: 'auto' }}>
              {activeThread.messages.slice().reverse().map((msg, idx) => (
                <div key={msg.id} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: idx < activeThread.messages.length - 1 ? '1px solid var(--bg-border)' : 'none' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.8rem' }}>
                    <span style={{ fontWeight: 500, color: msg.direction === 'inbound' ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {msg.direction === 'inbound' ? activeThread.lead_name : 'You'}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>{formatDate(msg.received_at)}</span>
                  </div>
                  {msg.body_html ? (
                    <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }} dangerouslySetInnerHTML={{ __html: msg.body_html }} />
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{msg.body_text}</div>
                  )}
                </div>
              ))}
            </div>

            <div className={styles.replyBox}>
              <textarea 
                className={styles.textarea} 
                placeholder="Type your reply here..."
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
              ></textarea>
              <div className={styles.replyActions}>
                <button className={styles.aiBtn}>
                  <Sparkles size={16} />
                  Draft AI Reply
                </button>
                <button 
                  className={styles.sendBtn} 
                  onClick={handleSendReply}
                  disabled={isSendingReply || !replyText.trim()}
                  style={{ opacity: isSendingReply ? 0.7 : 1, cursor: isSendingReply ? 'not-allowed' : 'pointer' }}
                >
                  <Send size={16} />
                  {isSendingReply ? "Sending..." : "Send"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
