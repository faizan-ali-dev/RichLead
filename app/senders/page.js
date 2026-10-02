"use client";

import { API_BASE, asList, clearTokens } from "../lib/api";

import styles from "./page.module.css";
import { Plus, MoreHorizontal, Mail, X } from "lucide-react";
import { useCallback, useState, useEffect } from "react";
import Image from "next/image"; // If you have local icons, or we can just use text
import { useFeedback } from "../../components/FeedbackProvider";

function describeInboxError(payload, status) {
  if (status === 401) return "Your session expired. Sign in again and retry.";
  if (status >= 500) return `The server could not add this inbox (HTTP ${status}).`;

  const errors = [];
  const collect = (field, value) => {
    const messages = Array.isArray(value) ? value : [value];
    for (const message of messages) {
      if (typeof message === "string") {
        errors.push(field ? `${field}: ${message}` : message);
      }
    }
  };

  if (payload && typeof payload === "object") {
    for (const [field, value] of Object.entries(payload)) {
      // Show DRF validation text only; never echo request values or secrets.
      const safeField = ["detail", "non_field_errors", "email_address", "smtp_host", "smtp_port", "imap_host", "imap_port", "auth_type"].includes(field)
        ? field
        : "request";
      collect(safeField === "detail" || safeField === "non_field_errors" ? "" : safeField, value);
    }
  }

  return errors.length
    ? `Could not add inbox (HTTP ${status}): ${errors.join(" ")}`
    : `Could not add inbox (HTTP ${status}).`;
}

export default function SendersPage() {
  const { notify, confirm } = useFeedback();
  const [senders, setSenders] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState("selection"); // 'selection' or 'custom_smtp'
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Custom SMTP Form State
  const [emailAddress, setEmailAddress] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [password, setPassword] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState(993);
  const [imapPassword, setImapPassword] = useState("");
  
  const [activeDropdown, setActiveDropdown] = useState(null); // ID of the sender whose dropdown is open
  
  const fetchSenders = useCallback(async (accessToken) => {
    try {
      const response = await fetch(`${API_BASE}/api/integrations/email-accounts/`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (response.status === 401) {
        clearTokens();
        window.location.href = "/login";
        return;
      }
      const data = asList(await response.json());
      if (Array.isArray(data)) {
        setSenders(data);
      }
    } catch (error) {
      console.error("Error fetching senders:", error);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const storedToken = localStorage.getItem("richlead_token");
      if (storedToken) {
        fetchSenders(storedToken);
      } else {
        window.location.href = "/login";
      }

      // Check URL parameters for OAuth success/error.
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get("success")) {
        notify("Your inbox was connected successfully.", { type: "success", title: "Inbox connected" });
        window.history.replaceState({}, document.title, window.location.pathname);
      } else if (urlParams.get("error")) {
        const errorMsg = urlParams.get("error");
        if (errorMsg === "invalid_client_credentials") {
          notify("Google or Microsoft OAuth credentials are missing or invalid in the server configuration.", { type: "error", title: "OAuth setup required" });
        } else {
          notify(errorMsg, { type: "error", title: "OAuth connection failed" });
        }
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchSenders, notify]);

  const handleOAuthConnect = async (provider) => {
    const accessToken = localStorage.getItem("richlead_token");
    if (!accessToken) return;
    try {
      const endpoint = provider === 'google' 
        ? `${API_BASE}/api/integrations/oauth/google/init/`
        : `${API_BASE}/api/integrations/oauth/microsoft/init/?prompt=login`;
        
      const response = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: "include",
      });
      
      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        notify(errData?.detail || errData?.error || `The server could not start OAuth (HTTP ${response.status}).`, { type: "error", title: "Could not connect inbox" });
        return;
      }

      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (error) {
      console.error(`Error initializing ${provider} OAuth:`, error);
      notify("A network error prevented the OAuth connection from starting.", { type: "error", title: "Could not connect inbox" });
    }
  };

  const handleAddCustomSMTP = async (e) => {
    e.preventDefault();
    const accessToken = localStorage.getItem("richlead_token");
    if (!accessToken) return;
    setIsSubmitting(true);
    
    try {
      const response = await fetch(`${API_BASE}/api/integrations/email-accounts/`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          email_address: emailAddress,
          provider: 'smtp',
          auth_type: 'smtp',
          smtp_host: smtpHost,
          smtp_port: smtpPort,
          password: password,
          imap_host: imapHost,
          imap_port: imapPort,
          imap_password: imapPassword
        })
      });
      
      if (response.ok) {
        const newAccount = await response.json();
        setSenders([...senders, newAccount]);
        setShowModal(false);
        setModalMode("selection");
        // Reset form
        setEmailAddress("");
        setSmtpHost("");
        setPassword("");
        notify("Your custom SMTP inbox was connected successfully.", { type: "success", title: "Inbox connected" });
      } else {
        const errorData = await response.json().catch(() => null);
        notify(describeInboxError(errorData, response.status), { type: "error", title: "Could not add inbox" });
      }
    } catch (error) {
      console.error("Error adding inbox:", error);
      notify("A network error prevented the inbox from being added.", { type: "error", title: "Could not add inbox" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusBadge = (isConnected) => {
    if (isConnected) {
      return <span className={`${styles.badge} ${styles.badgeActive}`}>Connected</span>;
    }
    return <span className={`${styles.badge} ${styles.badgePaused}`}>Disconnected</span>;
  };

  const handleDelete = async (id) => {
    if (!(await confirm({
      title: "Delete this inbox?",
      message: "This email account will be removed from RichLead. This action cannot be undone.",
      confirmLabel: "Delete inbox",
      variant: "danger",
    }))) return;
    const accessToken = localStorage.getItem("richlead_token");
    if (!accessToken) return;
    
    try {
      const response = await fetch(`${API_BASE}/api/integrations/email-accounts/${id}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (response.ok) {
        setSenders(senders.filter(s => s.id !== id));
        notify("The email account was deleted successfully.", { type: "success", title: "Inbox deleted" });
      } else {
        notify("The email account could not be deleted.", { type: "error", title: "Could not delete inbox" });
      }
    } catch (err) {
      console.error("Error deleting account:", err);
      notify("A network error prevented the email account from being deleted.", { type: "error", title: "Could not delete inbox" });
    } finally {
      setActiveDropdown(null);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.controls}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Sender Accounts</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Manage your inboxes for automated rotation and outreach.</p>
        </div>
        <button className={styles.addBtn} onClick={() => { setShowModal(true); setModalMode("selection"); }}>
          <Plus size={18} />
          Connect Inbox
        </button>
      </div>

      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Account</th>
              <th>Provider / Auth</th>
              <th>Host</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {senders.length === 0 ? (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                No sender accounts found. Click &quot;Connect Inbox&quot; to add one.
                </td>
              </tr>
            ) : senders.map((sender) => (
              <tr key={sender.id} className="animate-fade-in">
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Mail size={16} color="var(--text-secondary)" />
                    <span style={{ fontWeight: 500 }}>{sender.email_address}</span>
                  </div>
                </td>
                <td style={{ textTransform: 'capitalize' }}>
                  {sender.provider} <span style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>({sender.auth_type})</span>
                </td>
                <td>{sender.auth_type === 'smtp' ? `${sender.smtp_host}:${sender.smtp_port}` : 'OAuth Managed'}</td>
                <td>{getStatusBadge(sender.is_connected)}</td>
                <td style={{ position: 'relative' }}>
                  <button 
                    onClick={() => setActiveDropdown(activeDropdown === sender.id ? null : sender.id)}
                    style={{ color: "var(--text-secondary)", cursor: 'pointer', background: 'none', border: 'none' }}
                  >
                    <MoreHorizontal size={20} />
                  </button>
                  {activeDropdown === sender.id && (
                    <div className="animate-fade-in" style={{ position: 'absolute', right: '100%', top: '50%', transform: 'translateY(-50%)', background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', borderRadius: '6px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 10, minWidth: '120px', overflow: 'hidden' }}>
                      <button 
                        onClick={() => handleDelete(sender.id)}
                        style={{ width: '100%', padding: '0.75rem 1rem', background: 'none', border: 'none', color: 'var(--accent-danger)', textAlign: 'left', cursor: 'pointer', fontSize: '0.875rem', fontWeight: 500 }}
                      >
                        Delete Account
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="animate-fade-in" style={{ width: '100%', maxWidth: '450px', background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>
            
            <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--bg-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-primary)' }}>
                {modalMode === 'selection' ? 'Connect New Inbox' : 'Custom SMTP Setup'}
              </h3>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={20} /></button>
            </div>
            
            {modalMode === 'selection' ? (
              <div style={{ padding: '2rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <button 
                  onClick={() => handleOAuthConnect('google')}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', width: '100%', padding: '1rem', background: 'white', color: '#333', border: '1px solid #ddd', borderRadius: '8px', fontSize: '1rem', fontWeight: 600, cursor: 'pointer', transition: '0.2s', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}
                >
                  <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" role="img">
                    <path fill="#4285F4" d="M23.49 12.27c0-.78-.07-1.53-.2-2.27H12v4.51h6.44c-.28 1.45-1.12 2.68-2.39 3.51v2.93h3.87c2.26-2.08 3.57-5.14 3.57-8.68z" />
                    <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.92l-3.87-2.93c-1.08.72-2.46 1.15-4.06 1.15-3.12 0-5.77-2.1-6.72-4.93H1.29v3.02A12 12 0 0 0 12 24z" />
                    <path fill="#FBBC05" d="M5.28 14.37a7.2 7.2 0 0 1 0-4.74V6.61H1.29a12 12 0 0 0 0 10.78z" />
                    <path fill="#EA4335" d="M12 4.7c1.77 0 3.35.61 4.6 1.82l3.44-3.44C17.95 1.14 15.24 0 12 0A12 12 0 0 0 1.29 6.61l3.99 3.02C6.23 6.8 8.88 4.7 12 4.7z" />
                  </svg>
                  Continue with Google
                </button>
                
                <div>
                  <button 
                    onClick={() => handleOAuthConnect('microsoft')}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', width: '100%', padding: '1rem', background: '#0078D4', color: 'white', border: 'none', borderRadius: '8px', fontSize: '1rem', fontWeight: 600, cursor: 'pointer', transition: '0.2s', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}
                  >
                    <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" alt="Microsoft" width={24} height={24} />
                    Continue with Microsoft
                  </button>
                  <p style={{ margin: '0.4rem 0 0', fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                    Sign in with your <strong>@outlook.com</strong> account to ensure 100% email deliverability.
                  </p>
                </div>
                
                <div style={{ textAlign: 'center', margin: '1rem 0', position: 'relative' }}>
                  <hr style={{ border: 'none', borderTop: '1px solid var(--bg-border)' }} />
                  <span style={{ position: 'absolute', top: '-10px', left: '50%', transform: 'translateX(-50%)', background: 'var(--bg-surface)', padding: '0 10px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>or</span>
                </div>
                
                <button 
                  onClick={() => setModalMode('custom_smtp')}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', padding: '1rem', background: 'var(--bg-base)', color: 'var(--text-primary)', border: '1px solid var(--bg-border)', borderRadius: '8px', fontSize: '1rem', fontWeight: 600, cursor: 'pointer', transition: '0.2s' }}
                >
                  Configure Custom SMTP
                </button>
              </div>
            ) : (
              <form onSubmit={handleAddCustomSMTP} style={{ padding: '1.5rem' }}>
                <div style={{ marginBottom: '1.25rem' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Email Address</label>
                  <input 
                    type="email" 
                    required
                    value={emailAddress}
                    onChange={(e) => setEmailAddress(e.target.value)}
                    placeholder="e.g. hello@startup.com" 
                    style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>SMTP Host</label>
                    <input 
                      type="text" 
                      required
                      value={smtpHost}
                      onChange={(e) => setSmtpHost(e.target.value)}
                      placeholder="smtp.example.com" 
                      style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Port</label>
                    <input 
                      type="number" 
                      required
                      value={smtpPort}
                      onChange={(e) => setSmtpPort(Number(e.target.value))}
                      style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>SMTP Password</label>
                  <input 
                    type="password" 
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••••••" 
                    style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>IMAP Host (for receiving)</label>
                    <input 
                      type="text" 
                      value={imapHost}
                      onChange={(e) => setImapHost(e.target.value)}
                      placeholder="imap.example.com" 
                      style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>IMAP Port</label>
                    <input 
                      type="number" 
                      value={imapPort}
                      onChange={(e) => setImapPort(Number(e.target.value))}
                      style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>IMAP Password (Leave blank if same as SMTP)</label>
                  <input 
                    type="password" 
                    value={imapPassword}
                    onChange={(e) => setImapPassword(e.target.value)}
                    placeholder="••••••••••••••••" 
                    style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                  <button type="button" onClick={() => setModalMode('selection')} style={{ padding: '0.75rem 1.25rem', background: 'none', border: 'none', color: 'var(--text-secondary)', fontWeight: 500, cursor: 'pointer' }}>Back</button>
                  <button type="submit" disabled={isSubmitting} style={{ padding: '0.75rem 1.25rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1 }}>
                    {isSubmitting ? "Connecting..." : "Connect Inbox"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

    </div>
  );
}
