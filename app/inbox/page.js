"use client";

import { asList, authFetch, getAccessToken, redirectToLogin } from "../lib/api";
import { submitBackgroundJob } from "../lib/jobs";

import styles from "./page.module.css";
import { ArrowLeft, Mail, Send, Sparkles, MoreVertical, PanelLeft, RefreshCw } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useFeedback } from "../../components/FeedbackProvider";

// Reply-intent chip colours. Positive signals green, opt-outs red, neutral grey.
const INTENT_COLORS = {
  interested: { bg: "rgba(34,197,94,0.15)", fg: "var(--accent-success)" },
  referral: { bg: "rgba(34,197,94,0.12)", fg: "var(--accent-success)" },
  question: { bg: "rgba(99,102,241,0.15)", fg: "var(--accent-primary)" },
  not_now: { bg: "rgba(234,179,8,0.15)", fg: "#eab308" },
  out_of_office: { bg: "rgba(148,163,184,0.15)", fg: "var(--text-secondary)" },
  not_interested: { bg: "rgba(239,68,68,0.12)", fg: "var(--accent-danger)" },
  unsubscribe: { bg: "rgba(239,68,68,0.18)", fg: "var(--accent-danger)" },
  other: { bg: "rgba(148,163,184,0.12)", fg: "var(--text-muted)" },
};
const intentStyle = (intent) => {
  const c = INTENT_COLORS[intent] || INTENT_COLORS.other;
  return { background: c.bg, color: c.fg };
};


export default function InboxPage() {
  const { notify } = useFeedback();
  const [threads, setThreads] = useState([]);
  const [activeThread, setActiveThread] = useState(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [mobileThreadOpen, setMobileThreadOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [isSendingReply, setIsSendingReply] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const syncInFlight = useRef(false);
  const threadsRef = useRef([]);
  const pendingLeadId = useRef(null);

  const markThreadRead = useCallback(async (leadId) => {
    const updateThread = (thread) => thread.lead_id === leadId ? {
      ...thread,
      unread_count: 0,
      messages: thread.messages.map((message) => (
        message.direction === "inbound" ? { ...message, is_read: true } : message
      )),
    } : thread;
    threadsRef.current = threadsRef.current.map(updateThread);
    setThreads(threadsRef.current);
    setActiveThread((current) => current?.lead_id === leadId ? updateThread(current) : current);

    try {
      const response = await authFetch(`/api/inbox/${leadId}/read/`, { method: "POST" });
      if (response.ok) window.dispatchEvent(new Event("richlead-notifications-update"));
    } catch (error) {
      console.error("Could not mark conversation read", error);
    }
  }, []);

  const selectThread = useCallback((thread) => {
    setActiveThread(thread);
    setMobileThreadOpen(true);
    window.history.replaceState(null, "", "/inbox");
    if (thread.unread_count > 0) markThreadRead(thread.lead_id);
  }, [markThreadRead]);

  const openThreadByLeadId = useCallback((leadId) => {
    const normalizedId = Number(leadId);
    if (!Number.isInteger(normalizedId)) return;
    const thread = threadsRef.current.find((item) => item.lead_id === normalizedId);
    if (!thread) {
      pendingLeadId.current = normalizedId;
      return;
    }
    pendingLeadId.current = null;
    selectThread(thread);
  }, [selectThread]);

  const fetchInbox = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const response = await authFetch("/api/inbox/");
      if (response.ok) {
        const data = asList(await response.json());
        threadsRef.current = data;
        setThreads(data);
        const queryLeadValue = new URLSearchParams(window.location.search).get("lead");
        const queryLeadId = queryLeadValue ? Number(queryLeadValue) : null;
        const requestedLeadId = pendingLeadId.current || (Number.isInteger(queryLeadId) ? queryLeadId : null);
        const requestedThread = requestedLeadId
          ? data.find((thread) => thread.lead_id === requestedLeadId)
          : null;
        if (requestedThread) {
          pendingLeadId.current = null;
          setActiveThread(requestedThread);
          setMobileThreadOpen(true);
          window.history.replaceState(null, "", "/inbox");
          if (requestedThread.unread_count > 0) markThreadRead(requestedThread.lead_id);
        } else {
          if (requestedLeadId) pendingLeadId.current = requestedLeadId;
          setActiveThread((current) => {
            if (!data.length) return null;
            return data.find((thread) => thread.lead_id === current?.lead_id) || data[0];
          });
        }
        window.dispatchEvent(new Event("richlead-inbox-updated"));
      }
    } catch (err) {
      console.error("Failed to fetch inbox", err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [markThreadRead]);

  const triggerSync = useCallback(async (authToken) => {
    const t = authToken || getAccessToken();
    if (!t || syncInFlight.current) return;
    syncInFlight.current = true;
    setIsSyncing(true);
    try {
      await submitBackgroundJob("/api/inbox/sync/", {});
      await fetchInbox(true);
      setLastSyncedAt(new Date());
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
    }, 10 * 60_000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(interval);
    };
  }, [fetchInbox, triggerSync]);

  useEffect(() => {
    const openRequestedThread = (event) => openThreadByLeadId(event.detail?.leadId);
    window.addEventListener("richlead-open-inbox-thread", openRequestedThread);
    return () => window.removeEventListener("richlead-open-inbox-thread", openRequestedThread);
  }, [openThreadByLeadId]);

  const handleSync = () => triggerSync(getAccessToken());

  const handleSendReply = async () => {
    if (!replyText.trim() || !activeThread) return;
    setIsSendingReply(true);
    
    try {
      const data = await submitBackgroundJob("/api/integrations/send-email/", {
          lead_id: activeThread.lead_id,
          message: replyText
      });
      if (data.success) {
        notify("Your reply was sent successfully.", { type: "success", title: "Reply sent" });
        setReplyText("");
        // Reload inbox to show the sent message
        fetchInbox();
      } else {
        notify(data.error || "The reply could not be sent.", { type: "error", title: "Could not send reply" });
      }
    } catch (err) {
      notify(err.message || "A network error prevented the reply from being sent.", { type: "error", title: "Could not send reply" });
    } finally {
      setIsSendingReply(false);
    }
  };

  const formatDate = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  };

  return (
    <div className={`${styles.page} ${mobileThreadOpen ? styles.mobileThreadView : styles.mobileListView}`}>
      {showSidebar && (
        <div className={`${styles.sidebar} animate-fade-in`}>
        <div className={styles.sidebarHeader} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>
            Unified Inbox
            <span style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.7rem', fontWeight: 400, color: 'var(--text-muted)' }}>
              {isSyncing ? "Syncing mailboxes…" : lastSyncedAt ? `Auto-sync on · last sync ${lastSyncedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : "Auto-sync on · every 10 minutes"}
            </span>
          </span>
          <button 
            onClick={handleSync}
            disabled={isSyncing}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: isSyncing ? 'not-allowed' : 'pointer', opacity: isSyncing ? 0.5 : 1 }}
            title="Sync email now · automatic sync runs every 10 minutes"
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
            const latestInbound = thread.messages.find((m) => m.direction === "inbound" && m.intent);
            return (
              <div 
                key={thread.lead_id} 
                className={`${styles.messageItem} ${activeThread?.lead_id === thread.lead_id ? styles.active : ""}`}
                onClick={() => selectThread(thread)}
              >
                <div className={styles.msgName}>
                  {thread.lead_name}
                  <span className={styles.msgTime}>{latestMsg.received_at ? formatDate(latestMsg.received_at) : ''}</span>
                </div>
                <div className={styles.msgSubject}>{latestMsg.subject || 'No Subject'}</div>
                <div className={styles.msgPreview}>{latestMsg.body_text?.substring(0, 50) || '...'}</div>
                <div className={styles.threadMeta}>
                  <span>{thread.message_count} {thread.message_count === 1 ? "message" : "messages"}</span>
                  <span className={styles.threadBadges}>
                    {latestInbound && (
                      <span
                        className={styles.intentBadge}
                        style={intentStyle(latestInbound.intent)}
                        title={`Reply intent: ${latestInbound.intent_label}`}
                      >
                        {latestInbound.intent_label}
                      </span>
                    )}
                    {thread.mailbox_email && <span className={styles.mailboxBadge} title={`Mailbox: ${thread.mailbox_email}`}>{thread.mailbox_email}</span>}
                    {thread.unread_count > 0 && <span className={styles.unreadBadge} aria-label={`${thread.unread_count} unread replies`}>{thread.unread_count}</span>}
                  </span>
                </div>
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
                    className={styles.mobileBack}
                    onClick={() => { setMobileThreadOpen(false); setShowSidebar(true); }}
                    aria-label="Back to inbox conversations"
                  >
                    <ArrowLeft size={18} />
                  </button>
                  <button 
                    className={styles.desktopToggle}
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
                {activeThread.mailbox_email && <span className={styles.threadMailbox}>Mailbox: {activeThread.mailbox_email}</span>}
              </div>
            </div>

            <div className={styles.threadBody} style={{ overflowY: 'auto' }}>
              {activeThread.messages.slice().reverse().map((msg, idx) => (
                <div key={msg.id} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: idx < activeThread.messages.length - 1 ? '1px solid var(--bg-border)' : 'none' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.8rem' }}>
                    <span style={{ fontWeight: 500, color: msg.direction === 'inbound' ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {msg.direction === 'inbound' ? activeThread.lead_name : 'You'}
                      {msg.account_email && <span className={styles.messageMailbox}> · {msg.direction === 'inbound' ? 'received by' : 'sent via'} {msg.account_email}</span>}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>{formatDate(msg.received_at)}</span>
                  </div>
                  {msg.direction === 'inbound' && msg.reply_to_preview && (
                    <div className={styles.replyContext} title={msg.reply_to_preview}>
                      <strong>Replied to</strong>
                      <span>{msg.reply_to_preview}</span>
                    </div>
                  )}
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
