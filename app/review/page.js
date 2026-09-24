"use client";

import styles from "./page.module.css";
import { useState, useEffect } from "react";
import { Check, X, Send, Sparkles, RefreshCw, Mail } from "lucide-react";

export default function ReviewPage() {
  const [queueData, setQueueData] = useState([]);
  const [activeItem, setActiveItem] = useState(null);
  const [message, setMessage] = useState("");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showSignals, setShowSignals] = useState(false);
  const [showResearch, setShowResearch] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [emailAccounts, setEmailAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");

  useEffect(() => {
    const storedToken = localStorage.getItem("richlead_token");
    if (storedToken) {
      setToken(storedToken);
      fetchQueue(storedToken);
      fetchEmailAccounts(storedToken);
    } else {
      window.location.href = "/login";
    }
  }, []);

  const fetchEmailAccounts = async (accessToken) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/integrations/email-accounts/", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setEmailAccounts(data);
        if (data.length > 0) {
          setSelectedAccountId(data[0].id);
        }
      }
    } catch (error) {
      console.error("Error fetching accounts:", error);
    }
  };

  const fetchQueue = async (accessToken) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/leads/", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      
      if (response.status === 401) {
        localStorage.removeItem("richlead_token");
        window.location.href = "/login";
        return;
      }
      
      const data = await response.json();
      
      if (Array.isArray(data)) {
        // Filter only pending reviews
        const pending = data.filter(lead => lead.status === "pending");
        setQueueData(pending);
        if (pending.length > 0) {
          setActiveItem(pending[0]);
          setMessage(pending[0].research?.generated_message || pending[0].message || "");
        }
      } else {
        setQueueData([]);
      }
    } catch (error) {
      console.error("Error fetching queue:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!activeItem || !token) return;
    setIsRegenerating(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/ai/process-lead/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
        },
        body: JSON.stringify({ lead_id: activeItem.id })
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setMessage(data.message);
      } else {
        alert("Failed to regenerate: " + (data.error || "Unknown error"));
      }
    } catch (error) {
      console.error("Error regenerating:", error);
      alert("Error regenerating message.");
    } finally {
      setIsRegenerating(false);
    }
  };

  const [isSending, setIsSending] = useState(false);
  const [statusNotice, setStatusNotice] = useState(null);

  const handleApproveAndSend = async () => {
    if (!activeItem || !token) return;
    setStatusNotice(null);

    if (!message || !message.trim()) {
      setStatusNotice({ 
        type: 'error', 
        text: "Please write an email message or click 'Generate AI Draft' before approving!" 
      });
      const textarea = document.getElementById("message-textarea");
      if (textarea) {
        textarea.focus();
        textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    if (!selectedAccountId && emailAccounts.length > 0) {
      setStatusNotice({ 
        type: 'warning', 
        text: "Please select which email account to send from." 
      });
      return;
    }

    const currentAcc = emailAccounts.find(a => a.id === selectedAccountId);
    const senderName = selectedAccountId === 'rotate' 
      ? 'Auto-Rotating Inboxes' 
      : currentAcc ? currentAcc.email_address : 'Default Account';

    setIsSending(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/integrations/send-email/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
        },
        body: JSON.stringify({ 
          lead_id: activeItem.id, 
          message: message,
          account_id: selectedAccountId || null
        })
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setStatusNotice({ 
          type: 'success', 
          text: `Email successfully sent to ${activeItem.name} (${activeItem.email}) via ${senderName}!` 
        });
        // Remove from local queue
        const updatedQueue = queueData.filter(lead => lead.id !== activeItem.id);
        setQueueData(updatedQueue);
        if (updatedQueue.length > 0) {
          handleSelect(updatedQueue[0]);
        } else {
          setActiveItem(null);
          setMessage("");
        }
      } else {
        setStatusNotice({ 
          type: 'error', 
          text: "Failed to send email: " + (data.error || "Unknown error") 
        });
      }
    } catch (error) {
      console.error("Error sending email:", error);
      setStatusNotice({ 
        type: 'error', 
        text: "Network error sending email. Please check your connection." 
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleReject = async () => {
    if (!activeItem || !token) return;
    if (!window.confirm(`Reject outreach for ${activeItem.name}?`)) return;

    try {
      await fetch(`http://127.0.0.1:8000/api/leads/${activeItem.id}/`, {
        method: "PATCH",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
        },
        body: JSON.stringify({ status: "blacklisted" })
      });
      const updatedQueue = queueData.filter(lead => lead.id !== activeItem.id);
      setQueueData(updatedQueue);
      if (updatedQueue.length > 0) {
        handleSelect(updatedQueue[0]);
      } else {
        setActiveItem(null);
        setMessage("");
      }
    } catch (e) {
      console.error(e);
      alert("Network error rejecting lead.");
    }
  };

  const handleBulkApprove = async () => {
    if (selectedIds.size === 0 || !token) return;
    const leadsToSend = queueData.filter(l => selectedIds.has(l.id));
    const emptyCount = leadsToSend.filter(l => !l.message?.trim()).length;
    if (emptyCount > 0) {
      alert(`${emptyCount} of the selected leads have no drafted message. Please review and generate messages first.`);
      return;
    }
    const currentAcc = emailAccounts.find(a => a.id === selectedAccountId);
    const senderName = selectedAccountId === 'rotate' 
      ? 'Auto-Rotating Inboxes' 
      : currentAcc ? currentAcc.email_address : 'Default Account';

    if (!window.confirm(`Bulk send ${leadsToSend.length} emails via ${senderName}?`)) return;

    setIsSending(true);
    let sentCount = 0;
    for (const lead of leadsToSend) {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/integrations/send-email/", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}` 
          },
          body: JSON.stringify({ 
            lead_id: lead.id, 
            message: lead.message,
            account_id: selectedAccountId || null
          })
        });
        if (res.ok) sentCount++;
      } catch (e) {
        console.error("Bulk send err:", e);
      }
    }
    alert(`Successfully sent ${sentCount} of ${leadsToSend.length} emails!`);
    const remaining = queueData.filter(l => !selectedIds.has(l.id));
    setQueueData(remaining);
    setSelectedIds(new Set());
    if (remaining.length > 0) {
      handleSelect(remaining[0]);
    } else {
      setActiveItem(null);
      setMessage("");
    }
    setIsSending(false);
  };

  const handleSelect = (item) => {
    setActiveItem(item);
    setMessage(item.message || item.research?.generated_message || "");
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

  const selectedAccount = emailAccounts.find(a => a.id === selectedAccountId);
  const senderDisplayName = selectedAccountId === 'rotate'
    ? 'Auto-Rotate Inboxes'
    : selectedAccount ? selectedAccount.email_address : 'Default Account';

  return (
    <div className={styles.page}>
      <div className={styles.queueList}>
        <div className={styles.listHeader} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Pending Reviews ({queueData.length})</span>
          {selectedIds.size > 0 && (
            <button 
              className={styles.btnApprove} 
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', cursor: 'pointer' }}
              onClick={handleBulkApprove}
            >
              Approve ({selectedIds.size})
            </button>
          )}
        </div>
        <div className={styles.listContent}>
          {queueData.map((item) => (
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
                  style={{ marginTop: '0.25rem', cursor: 'pointer' }}
                />
                <div>
                  <div className={styles.leadName}>{item.name}</div>
                  <div className={styles.leadCompany}>{item.company}</div>
                  {!item.message?.trim() && (
                    <span style={{ fontSize: '0.675rem', color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)', padding: '0.1rem 0.35rem', borderRadius: '3px', marginTop: '0.25rem', display: 'inline-block' }}>
                      No draft yet
                    </span>
                  )}
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
                {item.icpScore || 0}
              </div>
            </div>
          ))}
          {queueData.length === 0 && (
            <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              🎉 All pending reviews complete!
            </div>
          )}
        </div>
      </div>

      {activeItem ? (
        <div className={`${styles.reviewPanel} animate-fade-in`}>
          <div className={styles.panelHeader}>
            <div className={styles.leadInfo}>
              <h2>{activeItem.name}</h2>
              <p>{activeItem.company} • <span style={{ color: 'var(--text-muted)' }}>{activeItem.email}</span></p>
            </div>
          </div>
          
          <div style={{ padding: '1.25rem 2rem 0' }}>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              {!showSignals ? (
                <button 
                  onClick={() => setShowSignals(true)}
                  style={{ background: 'var(--bg-surface-hover)', border: '1px solid var(--bg-border)', padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                  Show Detected Signals ({activeItem.intentSignals?.length || 0})
                </button>
              ) : (
                <div style={{ flex: '1 1 300px', padding: '1rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--bg-border)', position: 'relative' }}>
                  <button onClick={() => setShowSignals(false)} style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={14}/></button>
                  <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Detected Signals</h3>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {activeItem.intentSignals && activeItem.intentSignals.length > 0 ? (
                      activeItem.intentSignals.map((sig, i) => (
                        <li key={i} style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{sig}</li>
                      ))
                    ) : (
                      <li style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No signals detected yet.</li>
                    )}
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
                    {activeItem.researchSummary || "No research summary available. Click 'Regenerate AI' to analyze."}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Message Area */}
          <div className={styles.messageEditor} style={{ marginTop: '0.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                Generated Message
                {!message?.trim() && (
                  <span style={{ fontSize: '0.75rem', color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)', padding: '0.15rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
                    Draft Empty
                  </span>
                )}
              </label>
              
              <button 
                onClick={handleRegenerate}
                disabled={isRegenerating}
                style={{ 
                  background: 'none', 
                  border: 'none', 
                  color: 'var(--accent-primary)', 
                  cursor: isRegenerating ? 'not-allowed' : 'pointer', 
                  fontSize: '0.825rem', 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.4rem',
                  fontWeight: 600
                }}
              >
                <Sparkles size={14} />
                {isRegenerating ? "Generating..." : "Generate AI Draft"}
              </button>
            </div>

            {!message?.trim() && (
              <div style={{
                padding: '0.85rem 1rem',
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <Sparkles size={16} color="#f59e0b" />
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                    No outreach message has been drafted yet for <strong>{activeItem.name}</strong>.
                  </span>
                </div>
                <button
                  onClick={handleRegenerate}
                  disabled={isRegenerating}
                  style={{
                    padding: '0.4rem 0.85rem',
                    background: 'var(--accent-primary)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: isRegenerating ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    whiteSpace: 'nowrap'
                  }}
                >
                  <RefreshCw size={13} className={isRegenerating ? "animate-spin" : ""} />
                  {isRegenerating ? "Generating..." : "Generate AI Draft Now"}
                </button>
              </div>
            )}

            <textarea 
              id="message-textarea"
              className={styles.textarea}
              value={message}
              onChange={(e) => {
                setMessage(e.target.value);
                setActiveItem(prev => ({ ...prev, message: e.target.value }));
                setQueueData(prev => prev.map(l => l.id === activeItem.id ? { ...l, message: e.target.value } : l));
              }}
              placeholder="Type your outreach message here, or click 'Generate AI Draft' to let AI write a personalized email..."
              style={{ minHeight: '140px' }}
            />
          </div>

          {/* Status Notice Banner */}
          {statusNotice && (
            <div style={{
              margin: '0 2rem 1rem 2rem',
              padding: '0.8rem 1.2rem',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              backgroundColor: statusNotice.type === 'success' 
                ? 'rgba(16, 185, 129, 0.12)' 
                : statusNotice.type === 'error' 
                  ? 'rgba(239, 68, 68, 0.12)' 
                  : 'rgba(245, 158, 11, 0.12)',
              border: `1px solid ${statusNotice.type === 'success' 
                ? 'rgba(16, 185, 129, 0.4)' 
                : statusNotice.type === 'error' 
                  ? 'rgba(239, 68, 68, 0.4)' 
                  : 'rgba(245, 158, 11, 0.4)'}`,
              color: statusNotice.type === 'success' 
                ? '#10b981' 
                : statusNotice.type === 'error' 
                  ? '#ef4444' 
                  : '#f59e0b',
              fontSize: '0.875rem',
              fontWeight: 500
            }}>
              <span>{statusNotice.text}</span>
              <button 
                onClick={() => setStatusNotice(null)} 
                style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Sender Account Selection */}
          <div style={{ padding: '0 2rem 1.25rem 2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
              <label style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Mail size={15} color="var(--accent-primary)" /> Sending Inbox ({emailAccounts.length} Connected)
              </label>
              {emailAccounts.length > 1 && (
                <span style={{ fontSize: '0.725rem', color: 'var(--accent-primary)', background: 'rgba(99, 102, 241, 0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
                  Select an Inbox or Auto-Rotate
                </span>
              )}
            </div>

            {emailAccounts.length === 0 ? (
              <div style={{ padding: '0.75rem 1rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', fontSize: '0.85rem', color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>No connected email accounts found. Connect an inbox in <strong>Sender Accounts</strong>.</span>
                <a href="/senders" style={{ color: 'var(--accent-primary)', textDecoration: 'underline', fontWeight: 600, fontSize: '0.85rem' }}>Go to Senders →</a>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: emailAccounts.length > 1 ? 'repeat(auto-fit, minmax(210px, 1fr))' : '1fr', gap: '0.75rem' }}>
                {emailAccounts.map(acc => {
                  const isSelected = selectedAccountId === acc.id;
                  const isGoogle = acc.provider?.toLowerCase().includes('google') || acc.auth_type?.includes('google');
                  const isMicrosoft = acc.provider?.toLowerCase().includes('outlook') || acc.provider?.toLowerCase().includes('microsoft') || acc.auth_type?.includes('microsoft');
                  
                  return (
                    <div 
                      key={acc.id}
                      onClick={() => setSelectedAccountId(acc.id)}
                      style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '8px',
                        border: isSelected ? '2px solid var(--accent-primary)' : '1px solid var(--bg-border)',
                        background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'var(--bg-base)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        transition: 'all 0.2s ease',
                        boxShadow: isSelected ? '0 0 14px rgba(99, 102, 241, 0.2)' : 'none'
                      }}
                    >
                      <div style={{ 
                        width: '14px', 
                        height: '14px', 
                        borderRadius: '50%', 
                        border: isSelected ? '4px solid var(--accent-primary)' : '2px solid var(--text-muted)',
                        backgroundColor: isSelected ? 'white' : 'transparent',
                        flexShrink: 0
                      }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {acc.email_address}
                        </div>
                        <div style={{ fontSize: '0.725rem', color: isSelected ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
                          {isGoogle ? 'Google Mail' : isMicrosoft ? 'Microsoft Outlook' : acc.provider || 'Custom SMTP'}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {emailAccounts.length > 1 && (
                  <div 
                    onClick={() => setSelectedAccountId('rotate')}
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      border: selectedAccountId === 'rotate' ? '2px solid var(--accent-success)' : '1px solid var(--bg-border)',
                      background: selectedAccountId === 'rotate' ? 'rgba(16, 185, 129, 0.12)' : 'var(--bg-base)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                      transition: 'all 0.2s ease',
                      boxShadow: selectedAccountId === 'rotate' ? '0 0 14px rgba(16, 185, 129, 0.2)' : 'none'
                    }}
                  >
                    <div style={{ 
                      width: '14px', 
                      height: '14px', 
                      borderRadius: '50%', 
                      border: selectedAccountId === 'rotate' ? '4px solid var(--accent-success)' : '2px solid var(--text-muted)',
                      backgroundColor: selectedAccountId === 'rotate' ? 'white' : 'transparent',
                      flexShrink: 0
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        🔄 Auto-Rotate Inboxes
                      </div>
                      <div style={{ fontSize: '0.725rem', color: selectedAccountId === 'rotate' ? 'var(--accent-success)' : 'var(--text-secondary)' }}>
                        Alternate evenly across accounts
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Action Footer */}
          <div className={styles.actions}>
            <button 
              className={`${styles.btn} ${styles.btnReject}`}
              onClick={handleReject}
              style={{ cursor: 'pointer' }}
            >
              <X size={18} />
              Reject
            </button>
            <button 
              className={`${styles.btn} ${styles.btnRegenerate}`} 
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', color: 'var(--text-primary)', opacity: isRegenerating ? 0.7 : 1, cursor: isRegenerating ? 'not-allowed' : 'pointer' }}
              onClick={handleRegenerate}
              disabled={isRegenerating}
            >
              <RefreshCw size={18} className={isRegenerating ? "animate-spin" : ""} />
              {isRegenerating ? "Generating..." : "Regenerate AI"}
            </button>
            <button 
              className={`${styles.btn} ${styles.btnApprove}`}
              onClick={handleApproveAndSend}
              disabled={isSending}
              style={{ 
                opacity: isSending ? 0.7 : 1, 
                cursor: isSending ? 'not-allowed' : 'pointer',
                background: selectedAccountId === 'rotate' ? 'var(--accent-success)' : 'var(--accent-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                minWidth: '220px',
                justifyContent: 'center'
              }}
            >
              {isSending ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  Sending via {selectedAccountId === 'rotate' ? 'Auto-Rotate' : senderDisplayName.split('@')[0]}...
                </>
              ) : (
                <>
                  <Send size={18} />
                  {selectedAccountId === 'rotate' 
                    ? "Approve & Send via Auto-Rotate" 
                    : `Approve & Send via ${senderDisplayName}`}
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
          Select a lead from the pending queue to review.
        </div>
      )}
    </div>
  );
}
