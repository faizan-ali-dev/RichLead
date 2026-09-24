"use client";
import { Search, Filter, MoreHorizontal, X, Sparkles, Trash2, Ban, Mail, Send, CheckCircle2 } from "lucide-react";
import styles from "./page.module.css";
import { useState, useEffect } from "react";

export default function LeadsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLead, setSelectedLead] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newLead, setNewLead] = useState({ name: "", company: "", email: "", niche: "" });
  const [isAdding, setIsAdding] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  
  const [emailAccounts, setEmailAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [selectedRows, setSelectedRows] = useState([]);

  useEffect(() => {
    const fetchLeads = async () => {
      const storedToken = localStorage.getItem("richlead_token");
      if (!storedToken) {
        window.location.href = "/login";
        return;
      }
      
      try {
        const response = await fetch("http://127.0.0.1:8000/api/leads/", {
          headers: { Authorization: `Bearer ${storedToken}` }
        });
        
        if (response.status === 401) {
          localStorage.removeItem("richlead_token");
          window.location.href = "/login";
          return;
        }
        
        const data = await response.json();
        if (Array.isArray(data)) {
          setLeads(data);
        } else {
          setLeads([]);
        }
      } catch (error) {
        console.error("Error fetching leads:", error);
      } finally {
        setLoading(false);
      }
    };
    
    const fetchEmailAccounts = async () => {
      const storedToken = localStorage.getItem("richlead_token");
      try {
        const response = await fetch("http://127.0.0.1:8000/api/integrations/email-accounts/", {
          headers: { Authorization: `Bearer ${storedToken}` }
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

    fetchLeads();
    fetchEmailAccounts();
  }, []);

  useEffect(() => {
    const handleClickOutside = () => {
      setActiveDropdown(null);
    };
    if (activeDropdown !== null) {
      window.addEventListener("click", handleClickOutside);
    }
    return () => {
      window.removeEventListener("click", handleClickOutside);
    };
  }, [activeDropdown]);

  const handleAddLead = async (e) => {
    e.preventDefault();
    setIsAdding(true);
    
    const storedToken = localStorage.getItem("richlead_token");
    try {
      const response = await fetch("http://127.0.0.1:8000/api/leads/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${storedToken}`
        },
        body: JSON.stringify(newLead)
      });
      
      if (response.ok) {
        const addedLead = await response.json();
        setLeads([addedLead, ...leads]);
        setShowAddModal(false);
        setNewLead({ name: "", company: "", email: "", niche: "" });
      } else {
        const errorData = await response.json();
        alert(`Failed to add lead: ${JSON.stringify(errorData)}`);
      }
    } catch (error) {
      console.error("Failed to add lead", error);
      alert("Network error. Please try again.");
    } finally {
      setIsAdding(false);
    }
  };

  const handleGenerateMessage = async () => {
    if (!selectedLead) return;
    setIsGenerating(true);
    const storedToken = localStorage.getItem("richlead_token");
    
    try {
      const response = await fetch("http://127.0.0.1:8000/api/ai/research-and-draft/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${storedToken}`
        },
        body: JSON.stringify({ lead_id: selectedLead.id })
      });
      
      const data = await response.json();
      if (response.ok && data.success) {
        setSelectedLead({
          ...selectedLead,
          researchSummary: data.summary,
          message: data.message
        });
        // Optionally update in main leads array
        setLeads(leads.map(l => l.id === selectedLead.id ? {
          ...l, 
          researchSummary: data.summary,
          message: data.message
        } : l));
      } else {
        alert("Failed to generate message: " + (data.error || "Unknown error"));
      }
    } catch (err) {
      alert("Network error generating message.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedLead || !selectedLead.message) return;

    if (!selectedAccountId && emailAccounts.length > 0) {
      alert("Please select which email account to send from.");
      return;
    }

    const currentAcc = emailAccounts.find(a => a.id === selectedAccountId);
    const senderName = selectedAccountId === 'rotate' 
      ? 'Auto-Rotating Inboxes' 
      : currentAcc ? currentAcc.email_address : 'Default Account';

    if (emailAccounts.length > 1) {
      const confirmed = window.confirm(`Confirm Sending Email:\n\nTo: ${selectedLead.name} (${selectedLead.email})\nFrom: ${senderName}\n\nDo you want to proceed?`);
      if (!confirmed) return;
    }

    setIsSending(true);
    const storedToken = localStorage.getItem("richlead_token");
    
    try {
      const response = await fetch("http://127.0.0.1:8000/api/integrations/send-email/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${storedToken}`
        },
        body: JSON.stringify({
          lead_id: selectedLead.id,
          message: selectedLead.message,
          account_id: selectedAccountId || null
        })
      });
      
      const data = await response.json();
      if (response.ok && data.success) {
        alert(`Email sent successfully from ${senderName}!`);
        setSelectedLead({...selectedLead, status: 'reached'});
        setLeads(leads.map(l => l.id === selectedLead.id ? {...l, status: 'reached'} : l));
      } else {
        alert("Failed to send email: " + (data.error || "Unknown error"));
      }
    } catch (err) {
      alert("Network error sending email.");
    } finally {
      setIsSending(false);
    }
  };


  const handleDeleteLead = async (leadId) => {
    if (!window.confirm("Are you sure you want to delete this lead?")) return;
    
    const storedToken = localStorage.getItem("richlead_token");
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/leads/${leadId}/`, {
        method: "DELETE",
        headers: {
          "Authorization": `Bearer ${storedToken}`
        }
      });
      
      if (response.ok || response.status === 204) {
        setLeads(leads.filter(l => l.id !== leadId));
        setActiveDropdown(null);
      } else {
        alert("Failed to delete lead.");
      }
    } catch (error) {
      console.error("Error deleting lead:", error);
      alert("Network error while deleting.");
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Are you sure you want to delete ${selectedRows.length} leads?`)) return;
    const storedToken = localStorage.getItem("richlead_token");
    for (const leadId of selectedRows) {
      await fetch(`http://127.0.0.1:8000/api/leads/${leadId}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${storedToken}` }
      });
    }
    setLeads(leads.filter(l => !selectedRows.includes(l.id)));
    setSelectedRows([]);
  };

  const handleUpdateStatus = async (leadId, newStatus) => {
    const storedToken = localStorage.getItem("richlead_token");
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/leads/${leadId}/`, {
        method: "PATCH",
        headers: { 
          Authorization: `Bearer ${storedToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        setLeads(leads.map(l => l.id === leadId ? {...l, status: newStatus} : l));
      } else {
        const errData = await res.json();
        alert("Failed to update status: " + JSON.stringify(errData));
      }
    } catch(e) {
      console.error(e);
      alert("Network error.");
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "pending": return <span className={`${styles.badge} ${styles.badgePending}`}>Pending</span>;
      case "reached": return <span className={`${styles.badge} ${styles.badgeReached}`}>Reached Out</span>;
      case "replied": return <span className={`${styles.badge} ${styles.badgeReplied}`}>Replied</span>;
      case "blacklisted": return <span className={`${styles.badge} ${styles.badgeBlacklisted}`}>Blacklisted</span>;
      default: return null;
    }
  };

  const filteredLeads = leads.filter(lead => 
    lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    lead.company.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className={styles.page}>
      <div className={styles.controls}>
        <div className={styles.searchBox}>
          <Search size={18} color="var(--text-secondary)" />
          <input 
            type="text" 
            placeholder="Search leads..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className={styles.actionButtons}>
          {selectedRows.length > 0 && (
            <button 
              className={styles.filterBtn} 
              style={{ color: '#ef4444', borderColor: '#ef4444' }}
              onClick={handleBulkDelete}
            >
              <Trash2 size={18} />
              Delete Selected ({selectedRows.length})
            </button>
          )}
          <button className={styles.bulkBtn} onClick={() => setShowAddModal(true)}>
            + Add Lead
          </button>
          <button className={styles.filterBtn}>
            <Filter size={18} />
            Filters
          </button>
        </div>
      </div>

      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th style={{ width: '40px' }}>
                <input 
                  type="checkbox"
                  checked={selectedRows.length === filteredLeads.length && filteredLeads.length > 0}
                  onChange={(e) => {
                    if (e.target.checked) setSelectedRows(filteredLeads.map(l => l.id));
                    else setSelectedRows([]);
                  }}
                  style={{ cursor: 'pointer' }}
                />
              </th>
              <th>Name</th>
              <th>Email</th>
              <th>Company</th>
              <th>ICP Score</th>
              <th>Niche</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredLeads.map((lead, index) => (
              <tr 
                key={lead.id} 
                className="animate-fade-in"
                onClick={() => setSelectedLead(lead)}
                style={{ 
                  cursor: "pointer", 
                  backgroundColor: selectedRows.includes(lead.id) ? 'rgba(99, 102, 241, 0.05)' : '',
                  position: activeDropdown === lead.id ? 'relative' : 'static',
                  zIndex: activeDropdown === lead.id ? 50 : 1
                }}
              >
                <td onClick={(e) => e.stopPropagation()}>
                  <input 
                    type="checkbox"
                    checked={selectedRows.includes(lead.id)}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedRows([...selectedRows, lead.id]);
                      else setSelectedRows(selectedRows.filter(id => id !== lead.id));
                    }}
                    style={{ cursor: 'pointer' }}
                  />
                </td>
                <td>
                  <div style={{ fontWeight: 500 }}>{lead.name}</div>
                </td>
                <td style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                  {lead.email}
                </td>
                <td>{lead.company}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ 
                      fontWeight: 600, 
                      color: lead.icpScore > 80 ? 'var(--accent-success)' : lead.icpScore > 70 ? 'var(--accent-warning)' : 'var(--text-muted)' 
                    }}>
                      {lead.icpScore}
                    </span>
                    {lead.icpScore >= 85 && (
                      <span className={`${styles.badge} ${styles.badgeReached}`} style={{ padding: '0.1rem 0.4rem', fontSize: '0.7rem' }}>High Priority</span>
                    )}
                  </div>
                </td>
                <td>{lead.niche}</td>
                <td>{getStatusBadge(lead.status)}</td>
                <td style={{ position: "relative", overflow: "visible" }} onClick={(e) => e.stopPropagation()}>
                  <div className={styles.dropdownContainer}>
                    <button 
                      className={styles.actionIconBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveDropdown(activeDropdown === lead.id ? null : lead.id);
                      }}
                      title="Actions"
                    >
                      <MoreHorizontal size={18} />
                    </button>
                    {activeDropdown === lead.id && (
                      <div className={`${styles.actionDropdown} ${filteredLeads.length > 3 && index >= filteredLeads.length - 2 ? styles.actionDropdownUp : ''}`}>
                        <button 
                          className={styles.dropdownItem}
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            handleUpdateStatus(lead.id, 'blacklisted'); 
                            setActiveDropdown(null); 
                          }}
                        >
                          <Ban size={15} /> Blacklist
                        </button>
                        <div className={styles.dropdownDivider}></div>
                        <button 
                          className={`${styles.dropdownItem} ${styles.dropdownItemDanger}`}
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            handleDeleteLead(lead.id); 
                          }}
                        >
                          <Trash2 size={15} /> Delete
                        </button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedLead && (
        <div className={styles.modalOverlay} onClick={() => setSelectedLead(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h2 style={{ margin: 0, color: 'var(--text-primary)' }}>{selectedLead.name}</h2>
                  <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-secondary)' }}>{selectedLead.company} • {selectedLead.email}</p>
                </div>
                <button onClick={() => setSelectedLead(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                  <X size={20} />
                </button>
              </div>
            </div>
            
            <div className={styles.modalBody}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--bg-border)' }}>
                  <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>ICP Score</h3>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '2.5rem', fontWeight: 700, color: selectedLead.icpScore > 80 ? 'var(--accent-success)' : 'var(--accent-warning)' }}>{selectedLead.icpScore}</span>
                    <span style={{ color: 'var(--text-muted)' }}>/ 100</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {selectedLead.scoreBreakdown.map((item, idx) => (
                      <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{item.factor}</span>
                        <span style={{ fontWeight: 500 }}>{item.score}/{item.max}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ padding: '1rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--bg-border)' }}>
                  <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Buying / Intent Signals</h3>
                  {selectedLead.intentSignals.length > 0 ? (
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {selectedLead.intentSignals.map((signal, idx) => (
                        <li key={idx} style={{ fontSize: '0.875rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          {signal}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No recent signals detected.</div>
                  )}
                </div>
              </div>

              <div style={{ padding: '1rem', background: 'rgba(99, 102, 241, 0.05)', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
                <h3 style={{ fontSize: '0.875rem', color: 'var(--accent-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={16} /> AI Research Summary
                </h3>
                <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                  {selectedLead.researchSummary || "Not researched yet."}
                </p>
              </div>

              {selectedLead.message && (
                <div style={{ padding: '1rem', marginTop: '1.5rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--bg-border)' }}>
                  <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Drafted Email</h3>
                  <textarea 
                    value={selectedLead.message}
                    onChange={(e) => setSelectedLead({...selectedLead, message: e.target.value})}
                    style={{ width: '100%', height: '150px', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--bg-border)', background: 'var(--bg-surface)', color: 'var(--text-primary)', fontFamily: 'inherit', resize: 'vertical' }}
                  />
                  
                  {/* Sender Account Selection */}
                  <div style={{ marginTop: '1.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                      <label style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        <Mail size={15} color="var(--accent-primary)" /> Sending Inbox ({emailAccounts.length} Connected)
                      </label>
                      {emailAccounts.length > 1 && (
                        <span style={{ fontSize: '0.725rem', color: 'var(--accent-primary)', background: 'rgba(99, 102, 241, 0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
                          Select or Auto-Rotate
                        </span>
                      )}
                    </div>
                    
                    {emailAccounts.length === 0 ? (
                      <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '6px', fontSize: '0.85rem', color: '#ef4444' }}>
                        No connected inboxes found. Please go to <strong>Senders</strong> tab to connect Google or Microsoft.
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: emailAccounts.length > 1 ? 'repeat(auto-fit, minmax(200px, 1fr))' : '1fr', gap: '0.75rem' }}>
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
                                background: isSelected ? 'rgba(99, 102, 241, 0.08)' : 'var(--bg-surface)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                                transition: 'all 0.2s ease',
                                boxShadow: isSelected ? '0 0 12px rgba(99, 102, 241, 0.2)' : 'none'
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
                                <div style={{ fontSize: '0.725rem', color: 'var(--text-secondary)' }}>
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
                              background: selectedAccountId === 'rotate' ? 'rgba(16, 185, 129, 0.08)' : 'var(--bg-surface)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.75rem',
                              transition: 'all 0.2s ease',
                              boxShadow: selectedAccountId === 'rotate' ? '0 0 12px rgba(16, 185, 129, 0.2)' : 'none'
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
                              <div style={{ fontSize: '0.725rem', color: 'var(--text-secondary)' }}>
                                Alternate evenly across accounts
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Action Footer */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginTop: '1.25rem' }}>
                    <button 
                      onClick={handleSendEmail} 
                      disabled={isSending || !selectedAccountId}
                      style={{ 
                        padding: '0.7rem 1.4rem', 
                        background: 'var(--accent-success)', 
                        color: 'white', 
                        border: 'none', 
                        borderRadius: '6px', 
                        fontWeight: 600, 
                        fontSize: '0.9rem',
                        cursor: (isSending || !selectedAccountId) ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        opacity: (isSending || !selectedAccountId) ? 0.7 : 1,
                        boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)'
                      }}
                    >
                      <Send size={16} />
                      {isSending 
                        ? "Sending..." 
                        : selectedAccountId === 'rotate' 
                          ? "Send with Auto-Rotation" 
                          : `Send via ${emailAccounts.find(a => a.id === selectedAccountId)?.email_address || 'Selected Account'}`}
                    </button>
                  </div>
                </div>
              )}
            </div>
            
            <div className={styles.modalFooter}>
              <button className={styles.filterBtn} onClick={() => setSelectedLead(null)}>Close</button>
              <button 
                className={styles.bulkBtn} 
                onClick={handleGenerateMessage}
                disabled={isGenerating}
              >
                {isGenerating ? "Generating..." : "Generate AI Message"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAddModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="animate-fade-in" style={{ width: '100%', maxWidth: '450px', background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>
            
            <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--bg-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-primary)' }}>Add New Lead</h3>
              <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={20} /></button>
            </div>
            
            <form onSubmit={handleAddLead} style={{ padding: '1.5rem' }}>
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Full Name</label>
                <input 
                  type="text" required
                  value={newLead.name} onChange={(e) => setNewLead({...newLead, name: e.target.value})}
                  placeholder="e.g. John Doe" 
                  style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                />
              </div>
              
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Email Address</label>
                <input 
                  type="email" required
                  value={newLead.email} onChange={(e) => setNewLead({...newLead, email: e.target.value})}
                  placeholder="e.g. john@company.com" 
                  style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Company</label>
                  <input 
                    type="text" required
                    value={newLead.company} onChange={(e) => setNewLead({...newLead, company: e.target.value})}
                    placeholder="Company Inc." 
                    style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Niche</label>
                  <input 
                    type="text" required
                    value={newLead.niche} onChange={(e) => setNewLead({...newLead, niche: e.target.value})}
                    placeholder="e.g. SaaS, E-com" 
                    style={{ width: '100%', padding: '0.75rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button type="button" onClick={() => setShowAddModal(false)} style={{ padding: '0.75rem 1.25rem', background: 'none', border: 'none', color: 'var(--text-secondary)', fontWeight: 500, cursor: 'pointer' }}>Cancel</button>
                <button type="submit" disabled={isAdding} style={{ padding: '0.75rem 1.25rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: isAdding ? 'not-allowed' : 'pointer', opacity: isAdding ? 0.7 : 1 }}>
                  {isAdding ? "Adding..." : "Add Lead"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
