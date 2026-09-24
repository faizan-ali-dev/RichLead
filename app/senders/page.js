"use client";

import styles from "./page.module.css";
import { Plus, MoreHorizontal, Mail, X } from "lucide-react";
import { useState, useEffect } from "react";
import Image from "next/image"; // If you have local icons, or we can just use text

export default function SendersPage() {
  const [senders, setSenders] = useState([]);
  const [token, setToken] = useState(null);
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
  
  // Alert Status
  const [alertMsg, setAlertMsg] = useState("");

  useEffect(() => {
    const storedToken = localStorage.getItem("richlead_token");
    if (storedToken) {
      setToken(storedToken);
      fetchSenders(storedToken);
    } else {
      window.location.href = "/login";
    }
    
    // Check URL parameters for OAuth success/error
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("success")) {
      setAlertMsg("Inbox connected successfully!");
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlParams.get("error")) {
      const rawError = urlParams.get("error");
      const errorMsg = decodeURIComponent(rawError);
      if (errorMsg === "invalid_client_credentials") {
        setAlertMsg("OAuth setup required: Google/Microsoft Client IDs or Secrets are missing or invalid in backend .env.");
      } else {
        setAlertMsg(`OAuth Error: ${errorMsg}`);
      }
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const fetchSenders = async (accessToken) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/integrations/email-accounts/", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (response.status === 401) {
        localStorage.removeItem("richlead_token");
        window.location.href = "/login";
        return;
      }
      const data = await response.json();
      if (Array.isArray(data)) {
        setSenders(data);
      }
    } catch (error) {
      console.error("Error fetching senders:", error);
    }
  };

  const handleOAuthConnect = async (provider) => {
    if (!token) return;
    try {
      const endpoint = provider === 'google' 
        ? "http://127.0.0.1:8000/api/integrations/oauth/google/init/" 
        : "http://127.0.0.1:8000/api/integrations/oauth/microsoft/init/?prompt=login";
        
      const response = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        alert(`Failed to initialize OAuth (${response.status}): ${errData?.detail || errData?.error || "Server error"}`);
        return;
      }

      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (error) {
      console.error(`Error initializing ${provider} OAuth:`, error);
      alert("Network error connecting to backend.");
    }
  };

  const handleAddCustomSMTP = async (e) => {
    e.preventDefault();
    if (!token) return;
    setIsSubmitting(true);
    
    try {
      const response = await fetch("http://127.0.0.1:8000/api/integrations/email-accounts/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
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
        setAlertMsg("Custom SMTP inbox connected successfully!");
      } else {
        alert("Failed to add inbox.");
      }
    } catch (error) {
      console.error("Error adding inbox:", error);
      alert("Network error.");
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
    if (!confirm("Are you sure you want to delete this email account? This action cannot be undone.")) return;
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/integrations/email-accounts/${id}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        setSenders(senders.filter(s => s.id !== id));
        setAlertMsg("Account deleted successfully.");
      } else {
        alert("Failed to delete account.");
      }
    } catch (err) {
      console.error("Error deleting account:", err);
      alert("Network error while deleting.");
    } finally {
      setActiveDropdown(null);
    }
  };

  return (
    <div className={styles.page}>
      {alertMsg && (
        <div style={{ padding: '1rem', marginBottom: '1.5rem', borderRadius: '8px', background: alertMsg.includes('success') ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: alertMsg.includes('success') ? 'var(--accent-success)' : 'var(--accent-danger)', border: `1px solid ${alertMsg.includes('success') ? 'var(--accent-success)' : 'var(--accent-danger)'}` }}>
          {alertMsg}
        </div>
      )}

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
                  No sender accounts found. Click "Connect Inbox" to add one.
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
                  <img src="https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg" alt="Google" width={24} height={24} />
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
