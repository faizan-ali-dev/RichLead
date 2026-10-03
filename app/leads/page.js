"use client";

import { API_BASE, asList } from "../lib/api";
import { submitBackgroundJob } from "../lib/jobs";
import { Search, Filter, MoreHorizontal, X, Sparkles, Trash2, Ban, Mail, Send, CheckCircle2, SlidersHorizontal, RotateCcw } from "lucide-react";
import styles from "./page.module.css";
import { useState, useEffect, useCallback } from "react";
import { useFeedback } from "../../components/FeedbackProvider";
import { authFetch } from "../lib/api";

const EMPTY_LEAD = {
  name: "", email: "", company: "", title: "", niche: "", phone: "", industry: "",
  location: "", website: "", linkedin_url: "", employee_count: "", funding_amount: "",
  funding_round: "", funding_notes: "", icpScore: "0",
};

const EMPTY_FILTERS = {
  status: "all", source: "all", emailStatus: "all", minIcp: "all",
  employeeRange: "all", contactInfo: "all", industry: "", location: "",
};

const text = (value) => String(value ?? "").toLowerCase();

function normalizeOptionalUrl(value) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : null;
  } catch {
    return null;
  }
}

export default function LeadsPage() {
  const { notify, confirm } = useFeedback();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLead, setSelectedLead] = useState(null);
  const [leads, setLeads] = useState([]);
  const [leadTotal, setLeadTotal] = useState(0);
  const [leadPage, setLeadPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [hasPreviousPage, setHasPreviousPage] = useState(false);
  const [leadLoadError, setLeadLoadError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newLead, setNewLead] = useState(EMPTY_LEAD);
  const [isAdding, setIsAdding] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [sortBy, setSortBy] = useState("newest");
  
  const [emailAccounts, setEmailAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [selectedRows, setSelectedRows] = useState([]);

  const loadLeads = useCallback(async (pageNumber = 1, signal) => {
    setLoading(true);
    setLeadLoadError("");
    const params = new URLSearchParams({ page: String(pageNumber) });
    if (searchTerm.trim()) params.set("search", searchTerm.trim());
    if (filters.status !== "all") params.set("status", filters.status);
    if (filters.source !== "all") params.set("source", filters.source);
    if (filters.emailStatus !== "all") params.set("email_status", filters.emailStatus);
    if (filters.minIcp !== "all") params.set("min_icp", filters.minIcp);
    if (filters.employeeRange !== "all") params.set("employee_range", filters.employeeRange);
    if (filters.contactInfo !== "all") params.set("contact_info", filters.contactInfo);
    if (filters.industry.trim()) params.set("industry", filters.industry.trim());
    if (filters.location.trim()) params.set("location", filters.location.trim());
    params.set("ordering", sortBy === "icp_high" ? "-icp_score" : sortBy === "icp_low" ? "icp_score" : sortBy === "name" ? "name" : "-id");

    try {
      const response = await authFetch(`/api/leads/?${params.toString()}`, { signal });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "The leads could not be loaded.");
      const rows = Array.isArray(payload.results) ? payload.results : asList(payload);
      setLeads(rows);
      setLeadTotal(Number(payload.count ?? rows.length));
      setHasNextPage(Boolean(payload.next));
      setHasPreviousPage(Boolean(payload.previous));
      setLeadPage(pageNumber);
    } catch (error) {
      if (error.name === "AbortError") return;
      setLeadLoadError(error.message || "The leads could not be loaded.");
      setLeads([]);
      setLeadTotal(0);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [filters, searchTerm, sortBy]);

  useEffect(() => {
    const controller = new AbortController();
    const needsDebounce = Boolean(searchTerm.trim() || filters.industry.trim() || filters.location.trim());
    const timer = window.setTimeout(() => { loadLeads(leadPage, controller.signal); }, needsDebounce ? 250 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [loadLeads, leadPage, searchTerm, filters.industry, filters.location]);

  const updateFilters = (changes) => {
    setFilters((current) => ({ ...current, ...changes }));
    setLeadPage(1);
    setSelectedRows([]);
  };

  useEffect(() => {
    const fetchEmailAccounts = async () => {
      const storedToken = localStorage.getItem("richlead_token");
      try {
        const response = await fetch(`${API_BASE}/api/integrations/email-accounts/`, {
          headers: { Authorization: `Bearer ${storedToken}` }
        });
        if (response.ok) {
          const data = asList(await response.json());
          setEmailAccounts(data);
          if (data.length > 0) {
            setSelectedAccountId(data[0].id);
          }
        }
      } catch (error) {
        console.error("Error fetching accounts:", error);
      }
    };

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
    const website = normalizeOptionalUrl(newLead.website);
    const linkedinUrl = normalizeOptionalUrl(newLead.linkedin_url);
    if (website === null || linkedinUrl === null) {
      notify("Enter a valid website or LinkedIn URL. You can enter it with or without https://.", { type: "error", title: "Check the URL" });
      return;
    }
    setIsAdding(true);
    
    const storedToken = localStorage.getItem("richlead_token");
    try {
      const { funding_notes, employee_count, icpScore, ...leadFields } = newLead;
      const response = await fetch(`${API_BASE}/api/leads/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${storedToken}`
        },
        body: JSON.stringify({
          ...leadFields,
          source: "manual",
          website,
          linkedin_url: linkedinUrl,
          employee_count: employee_count === "" ? null : Number(employee_count),
          icpScore: Number(icpScore || 0),
          funding_data: funding_notes.trim() ? { notes: funding_notes.trim() } : {},
        })
      });
      
      if (response.ok) {
        await response.json();
        setShowAddModal(false);
        setNewLead(EMPTY_LEAD);
        setSelectedRows([]);
        setLeadPage(1);
        await loadLeads(1);
      } else {
        const errorData = await response.json();
        notify(`The lead could not be added: ${JSON.stringify(errorData)}`, { type: "error", title: "Could not add lead" });
      }
    } catch (error) {
      console.error("Failed to add lead", error);
      notify("A network error prevented the lead from being added. Please try again.", { type: "error", title: "Could not add lead" });
    } finally {
      setIsAdding(false);
    }
  };

  const handleGenerateMessage = async () => {
    if (!selectedLead) return;
    setIsGenerating(true);
    try {
      const data = await submitBackgroundJob("/api/ai/research-and-draft/", {
        lead_id: selectedLead.id,
      });
      if (data.success) {
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
        notify(data.error || "The message could not be generated.", { type: "error", title: "Could not generate message" });
      }
    } catch (err) {
      notify(err.message || "A network error prevented the message from being generated.", { type: "error", title: "Could not generate message" });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedLead || !selectedLead.message) return;

    if (!selectedAccountId && emailAccounts.length > 0) {
      notify("Choose an email account before sending this message.", { type: "warning", title: "Select a sending account" });
      return;
    }

    const currentAcc = emailAccounts.find(a => a.id === selectedAccountId);
    const senderName = selectedAccountId === 'rotate' 
      ? 'Auto-Rotating Inboxes' 
      : currentAcc ? currentAcc.email_address : 'Default Account';

    if (emailAccounts.length > 1) {
      const confirmed = await confirm({
        title: "Send this email?",
        message: `To: ${selectedLead.name} (${selectedLead.email})\nFrom: ${senderName}`,
        confirmLabel: "Send email",
      });
      if (!confirmed) return;
    }

    setIsSending(true);
    try {
      const data = await submitBackgroundJob("/api/integrations/send-email/", {
          lead_id: selectedLead.id,
          message: selectedLead.message,
          account_id: selectedAccountId || null
      });
      if (data.success) {
        notify(`Email sent successfully from ${senderName}.`, { type: "success", title: "Email sent" });
        setSelectedLead({...selectedLead, status: 'reached'});
        setLeads(leads.map(l => l.id === selectedLead.id ? {...l, status: 'reached'} : l));
      } else {
        notify(data.error || "The email could not be sent.", { type: "error", title: "Could not send email" });
      }
    } catch (err) {
      notify(err.message || "A network error prevented the email from being sent.", { type: "error", title: "Could not send email" });
    } finally {
      setIsSending(false);
    }
  };


  const handleDeleteLead = async (leadId) => {
    if (!(await confirm({ title: "Delete this lead?", message: "This lead will be permanently removed.", confirmLabel: "Delete lead", variant: "danger" }))) return;
    
    const storedToken = localStorage.getItem("richlead_token");
    try {
      const response = await fetch(`${API_BASE}/api/leads/${leadId}/`, {
        method: "DELETE",
        headers: {
          "Authorization": `Bearer ${storedToken}`
        }
      });
      
      if (response.ok || response.status === 204) {
        setLeads(leads.filter(l => l.id !== leadId));
        setLeadTotal((total) => Math.max(0, total - 1));
        setSelectedRows((selected) => selected.filter((id) => id !== leadId));
        setActiveDropdown(null);
      } else {
        notify("The lead could not be deleted.", { type: "error", title: "Could not delete lead" });
      }
    } catch (error) {
      console.error("Error deleting lead:", error);
      notify("A network error prevented the lead from being deleted.", { type: "error", title: "Could not delete lead" });
    }
  };

  const handleBulkDelete = async () => {
    if (!(await confirm({ title: `Delete ${selectedRows.length} leads?`, message: "These leads will be permanently removed.", confirmLabel: "Delete leads", variant: "danger" }))) return;
    const storedToken = localStorage.getItem("richlead_token");
    for (const leadId of selectedRows) {
      await fetch(`${API_BASE}/api/leads/${leadId}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${storedToken}` }
      });
    }
    setLeads(leads.filter(l => !selectedRows.includes(l.id)));
    setLeadTotal((total) => Math.max(0, total - selectedRows.length));
    setSelectedRows([]);
  };

  const handleUpdateStatus = async (leadId, newStatus) => {
    const storedToken = localStorage.getItem("richlead_token");
    try {
      const res = await fetch(`${API_BASE}/api/leads/${leadId}/`, {
        method: "PATCH",
        headers: { 
          Authorization: `Bearer ${storedToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        setLeads(leads.map(l => l.id === leadId ? {...l, status: newStatus} : l));
        await loadLeads(leadPage);
      } else {
        const errData = await res.json();
        notify(`The status could not be updated: ${JSON.stringify(errData)}`, { type: "error", title: "Could not update status" });
      }
    } catch(e) {
      console.error(e);
      notify("A network error prevented the status from being updated.", { type: "error", title: "Could not update status" });
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

  const activeFilterCount = Object.entries(filters).filter(([key, value]) => value !== EMPTY_FILTERS[key]).length + (searchTerm.trim() ? 1 : 0);
  const filteredLeads = leads;

  return (
    <div className={styles.page}>
      <div className={styles.controls}>
        <div className={styles.searchBox}>
          <Search size={18} color="var(--text-secondary)" />
          <input 
            type="text" 
            placeholder="Search name, company, email, phone, industry..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setLeadPage(1); setSelectedRows([]); }}
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
          <button className={styles.filterBtn} type="button" onClick={() => setFiltersOpen((open) => !open)} aria-expanded={filtersOpen}>
            <Filter size={18} />
            Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
          </button>
        </div>
      </div>

      {filtersOpen && (
        <section className={styles.filtersPanel} aria-label="Lead filters">
          <div className={styles.filterFields}>
            <label className={styles.filterField}>Outreach status
              <select value={filters.status} onChange={(e) => updateFilters({ status: e.target.value })}>
                <option value="all">All statuses</option>
                <option value="pending">Pending</option>
                <option value="reached">Reached out</option>
                <option value="replied">Replied</option>
                <option value="blacklisted">Blacklisted</option>
              </select>
            </label>
            <label className={styles.filterField}>Data source
              <select value={filters.source} onChange={(e) => updateFilters({ source: e.target.value })}>
                <option value="all">All sources</option>
                {[...new Set(["apollo", "hunter", "manual", ...leads.map((lead) => text(lead.source)).filter(Boolean)])].sort().map((source) => (
                  <option value={source} key={source}>{source === "manual" ? "Manual entry" : source.charAt(0).toUpperCase() + source.slice(1)}</option>
                ))}
              </select>
            </label>
            <label className={styles.filterField}>Email verification
              <select value={filters.emailStatus} onChange={(e) => updateFilters({ emailStatus: e.target.value })}>
                <option value="all">All email statuses</option>
                <option value="verified">Provider verified</option>
                <option value="unknown">Not checked</option>
                <option value="not_verified">Not verified</option>
              </select>
            </label>
            <label className={styles.filterField}>Minimum ICP score
              <select value={filters.minIcp} onChange={(e) => updateFilters({ minIcp: e.target.value })}>
                <option value="all">Any score</option>
                <option value="50">50 or higher</option>
                <option value="70">70 or higher</option>
                <option value="80">80 or higher</option>
                <option value="90">90 or higher</option>
              </select>
            </label>
            <label className={styles.filterField}>Company size
              <select value={filters.employeeRange} onChange={(e) => updateFilters({ employeeRange: e.target.value })}>
                <option value="all">Any size</option>
                <option value="1-10">1–10 employees</option>
                <option value="11-50">11–50 employees</option>
                <option value="51-200">51–200 employees</option>
                <option value="201+">201+ employees</option>
              </select>
            </label>
            <label className={styles.filterField}>Contact details
              <select value={filters.contactInfo} onChange={(e) => updateFilters({ contactInfo: e.target.value })}>
                <option value="all">Any contact details</option>
                <option value="has_phone">Has phone number</option>
                <option value="no_phone">Missing phone number</option>
                <option value="has_website">Has website</option>
                <option value="no_website">Missing website</option>
              </select>
            </label>
            <label className={styles.filterField}>Industry contains
              <input type="search" value={filters.industry} onChange={(e) => updateFilters({ industry: e.target.value })} placeholder="e.g. Software" />
            </label>
            <label className={styles.filterField}>Location contains
              <input type="search" value={filters.location} onChange={(e) => updateFilters({ location: e.target.value })} placeholder="e.g. London" />
            </label>
          </div>
          <button type="button" className={styles.clearFilters} onClick={() => { setFilters(EMPTY_FILTERS); setSearchTerm(""); setSortBy("newest"); setLeadPage(1); setSelectedRows([]); }} disabled={activeFilterCount === 0 && !searchTerm && sortBy === "newest"}>
            <RotateCcw size={14} /> Clear filters
          </button>
        </section>
      )}

      <div className={styles.resultsBar}>
        <span>{filteredLeads.length ? `Showing ${(leadPage - 1) * 50 + 1}–${Math.min(leadPage * 50, leadTotal)} of ${leadTotal}` : `${leadTotal} matching`} leads</span>
        <label className={styles.sortControl}><SlidersHorizontal size={15} /> Sort by
          <select value={sortBy} onChange={(e) => { setSortBy(e.target.value); setLeadPage(1); }} aria-label="Sort leads">
            <option value="newest">Recently added</option>
            <option value="icp_high">ICP score: high to low</option>
            <option value="icp_low">ICP score: low to high</option>
            <option value="name">Name: A to Z</option>
          </select>
        </label>
      </div>

      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th style={{ width: '40px' }}>
                <input 
                  type="checkbox"
                  checked={filteredLeads.length > 0 && filteredLeads.every((lead) => selectedRows.includes(lead.id))}
                  onChange={(e) => {
                    if (e.target.checked) setSelectedRows((current) => [...new Set([...current, ...filteredLeads.map((lead) => lead.id)])]);
                    else setSelectedRows((current) => current.filter((id) => !filteredLeads.some((lead) => lead.id === id)));
                  }}
                  style={{ cursor: 'pointer' }}
                />
              </th>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Company</th>
              <th>ICP Score</th>
              <th>Niche</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredLeads.length === 0 ? (
              <tr><td colSpan="9" className={styles.emptyResults}>{loading ? "Loading leads…" : leadLoadError || "No leads match these filters. Clear the filters or add a lead."}</td></tr>
            ) : filteredLeads.map((lead, index) => (
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
                <td style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>{lead.phone || "—"}</td>
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

      <div className={styles.paginationBar}>
        <span>Page {leadPage} · {leadTotal} matching leads</span>
        <div>
          <button type="button" className={styles.filterBtn} disabled={!hasPreviousPage || loading} onClick={() => setLeadPage((page) => Math.max(1, page - 1))}>Previous</button>
          <button type="button" className={styles.filterBtn} disabled={!hasNextPage || loading} onClick={() => setLeadPage((page) => page + 1)}>Next</button>
        </div>
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
              <section style={{ padding: '1rem', marginBottom: '1.5rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--bg-border)' }}>
                <h3 style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', margin: '0 0 0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Contact &amp; Company Details</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
                  {[
                    ['Job title', selectedLead.title],
                    ['Niche', selectedLead.niche],
                    ['Phone', selectedLead.phone],
                    ['Website', selectedLead.website],
                    ['LinkedIn', selectedLead.linkedin_url],
                    ['Industry', selectedLead.industry],
                    ['Location', selectedLead.location],
                    ['Employees', selectedLead.employee_count],
                    ['Funding', selectedLead.funding_amount],
                    ['Funding round', selectedLead.funding_round],
                    ['Funding context', selectedLead.funding_data?.notes],
                    ['Email verification', selectedLead.email_status === 'verified' ? 'Provider verified' : selectedLead.email_status === 'not_verified' ? 'Not verified' : 'Not checked'],
                    ['Data source', selectedLead.source],
                  ].map(([label, value]) => (
                    <div key={label} style={{ minWidth: 0 }}>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '0.2rem' }}>{label}</div>
                      <div style={{ color: 'var(--text-primary)', fontSize: '0.875rem', overflowWrap: 'anywhere' }}>
                        {value ? (label === 'Website' || label === 'LinkedIn'
                          ? <a href={String(value).startsWith('http') ? value : `https://${value}`} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)' }}>{value}</a>
                          : value)
                          : '—'}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
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
        <div className={styles.modalOverlay} onMouseDown={(event) => { if (event.target === event.currentTarget && !isAdding) setShowAddModal(false); }}>
          <section className={`${styles.modal} ${styles.addLeadModal}`} role="dialog" aria-modal="true" aria-labelledby="add-lead-title">
            <div className={styles.addLeadHeader}>
              <div>
                <h2 id="add-lead-title">Add a lead</h2>
                <p>Capture contact, company, funding, and fit details in one place.</p>
              </div>
              <button type="button" className={styles.closeModalButton} onClick={() => setShowAddModal(false)} disabled={isAdding} aria-label="Close add lead form"><X size={18} /></button>
            </div>

            <form onSubmit={handleAddLead} className={styles.leadForm}>
              <div className={styles.formSection}>
                <h3>Contact</h3>
                <div className={styles.addLeadGrid}>
                  <label className={`${styles.formField} ${styles.fieldWide}`}>Full name <span className={styles.required}>Required</span>
                    <input className={styles.formInput} type="text" required autoComplete="name" value={newLead.name} onChange={(e) => setNewLead({ ...newLead, name: e.target.value })} placeholder="e.g. Jordan Lee" />
                  </label>
                  <label className={`${styles.formField} ${styles.fieldWide}`}>Work email <span className={styles.required}>Required</span>
                    <input className={styles.formInput} type="email" required autoComplete="email" value={newLead.email} onChange={(e) => setNewLead({ ...newLead, email: e.target.value })} placeholder="jordan@company.com" />
                    <small>Manual addresses stay marked “Not checked” until a provider verifies them.</small>
                  </label>
                  <label className={styles.formField}>Phone number
                    <input className={styles.formInput} type="tel" autoComplete="tel" value={newLead.phone} onChange={(e) => setNewLead({ ...newLead, phone: e.target.value })} placeholder="+1 555 0100" />
                  </label>
                  <label className={styles.formField}>Job title
                    <input className={styles.formInput} type="text" autoComplete="organization-title" value={newLead.title} onChange={(e) => setNewLead({ ...newLead, title: e.target.value })} placeholder="Founder, VP of Sales" />
                  </label>
                </div>
              </div>

              <div className={styles.formSection}>
                <h3>Company</h3>
                <div className={styles.addLeadGrid}>
                  <label className={styles.formField}>Company name <span className={styles.required}>Required</span>
                    <input className={styles.formInput} type="text" required autoComplete="organization" value={newLead.company} onChange={(e) => setNewLead({ ...newLead, company: e.target.value })} placeholder="Company name" />
                  </label>
                  <label className={styles.formField}>Niche <span className={styles.required}>Required</span>
                    <input className={styles.formInput} type="text" required value={newLead.niche} onChange={(e) => setNewLead({ ...newLead, niche: e.target.value })} placeholder="SaaS, ecommerce" />
                  </label>
                  <label className={styles.formField}>Industry
                    <input className={styles.formInput} type="text" value={newLead.industry} onChange={(e) => setNewLead({ ...newLead, industry: e.target.value })} placeholder="Software, healthcare" />
                  </label>
                  <label className={styles.formField}>Location
                    <input className={styles.formInput} type="text" autoComplete="address-level2" value={newLead.location} onChange={(e) => setNewLead({ ...newLead, location: e.target.value })} placeholder="City, country" />
                  </label>
                  <label className={styles.formField}>Website
                    <input className={styles.formInput} type="text" inputMode="url" value={newLead.website} onChange={(e) => setNewLead({ ...newLead, website: e.target.value })} placeholder="company.com" />
                  </label>
                  <label className={styles.formField}>LinkedIn profile or company page
                    <input className={styles.formInput} type="text" inputMode="url" value={newLead.linkedin_url} onChange={(e) => setNewLead({ ...newLead, linkedin_url: e.target.value })} placeholder="linkedin.com/in/..." />
                  </label>
                  <label className={styles.formField}>Employee count
                    <input className={styles.formInput} type="number" min="0" step="1" value={newLead.employee_count} onChange={(e) => setNewLead({ ...newLead, employee_count: e.target.value })} placeholder="e.g. 45" />
                  </label>
                </div>
              </div>

              <div className={styles.formSection}>
                <h3>Funding and fit</h3>
                <div className={styles.addLeadGrid}>
                  <label className={styles.formField}>Funding amount
                    <input className={styles.formInput} type="text" value={newLead.funding_amount} onChange={(e) => setNewLead({ ...newLead, funding_amount: e.target.value })} placeholder="e.g. $5M" />
                  </label>
                  <label className={styles.formField}>Funding round
                    <input className={styles.formInput} type="text" value={newLead.funding_round} onChange={(e) => setNewLead({ ...newLead, funding_round: e.target.value })} placeholder="Seed, Series A" />
                  </label>
                  <label className={styles.formField}>ICP score <span className={styles.optional}>0 to 100</span>
                    <input className={styles.formInput} type="number" min="0" max="100" step="1" value={newLead.icpScore} onChange={(e) => setNewLead({ ...newLead, icpScore: e.target.value })} />
                    <small>Set your fit score manually. This does not claim email verification.</small>
                  </label>
                  <label className={`${styles.formField} ${styles.fieldWide}`}>Funding context
                    <textarea className={styles.formInput} rows="3" value={newLead.funding_notes} onChange={(e) => setNewLead({ ...newLead, funding_notes: e.target.value })} placeholder="Optional notes or source context about funding" />
                  </label>
                </div>
              </div>

              <div className={styles.addLeadFooter}>
                <span>Source will be saved as Manual. New leads start in Pending.</span>
                <div>
                  <button type="button" className={styles.filterBtn} onClick={() => setShowAddModal(false)} disabled={isAdding}>Cancel</button>
                  <button type="submit" className={styles.bulkBtn} disabled={isAdding}>{isAdding ? "Adding lead…" : "Add lead"}</button>
                </div>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
