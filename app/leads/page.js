"use client";

import styles from "./page.module.css";
import { Search, Filter, MoreHorizontal, X, Sparkles } from "lucide-react";
import { useState } from "react";

const LEADS_DATA = [
  { 
    id: 1, 
    name: "Alice Johnson", 
    company: "TechCorp", 
    niche: "SaaS", 
    status: "replied", 
    email: "alice@techcorp.com",
    icpScore: 92,
    intentSignals: ["🔥 Recently funded ($5M Series A)", "🚀 Hiring 5 new Sales Reps"],
    researchSummary: "TechCorp is scaling aggressively post-funding. They are likely struggling to build enough pipeline with their new sales team.",
    scoreBreakdown: [
      { factor: "Company Fit", score: 25, max: 25 },
      { factor: "Job Title", score: 20, max: 20 },
      { factor: "Industry", score: 18, max: 20 },
      { factor: "Company Size", score: 15, max: 15 },
      { factor: "Intent Signal", score: 14, max: 20 }
    ]
  },
  { 
    id: 2, 
    name: "Bob Smith", 
    company: "Innovate Inc", 
    niche: "E-commerce", 
    status: "reached", 
    email: "bob@innovate.com",
    icpScore: 85,
    intentSignals: ["📈 Website visit detected"],
    researchSummary: "Innovate Inc has seen a 20% drop in cart abandonment but needs better retention.",
    scoreBreakdown: [
      { factor: "Company Fit", score: 22, max: 25 },
      { factor: "Job Title", score: 20, max: 20 },
      { factor: "Industry", score: 15, max: 20 },
      { factor: "Company Size", score: 15, max: 15 },
      { factor: "Intent Signal", score: 13, max: 20 }
    ]
  },
  { 
    id: 3, 
    name: "Charlie Davis", 
    company: "Growthify", 
    niche: "Marketing", 
    status: "pending", 
    email: "charlie@growthify.com",
    icpScore: 78,
    intentSignals: ["💼 New CMO appointed"],
    researchSummary: "Growthify brought on a new CMO last month, likely restructuring their martech stack.",
    scoreBreakdown: [
      { factor: "Company Fit", score: 20, max: 25 },
      { factor: "Job Title", score: 15, max: 20 },
      { factor: "Industry", score: 18, max: 20 },
      { factor: "Company Size", score: 10, max: 15 },
      { factor: "Intent Signal", score: 15, max: 20 }
    ]
  },
  { id: 4, name: "Diana Prince", company: "Amazon", niche: "Retail", status: "reached", email: "diana@amazon.com", icpScore: 65, intentSignals: [], researchSummary: "Too large for standard enterprise motion, low priority.", scoreBreakdown: [] },
  { id: 5, name: "Evan Wright", company: "Stripe", niche: "Fintech", status: "pending", email: "evan@stripe.com", icpScore: 88, intentSignals: ["🚀 New product launch"], researchSummary: "Expanding their billing products, ideal timing for sales tooling.", scoreBreakdown: [] },
];

export default function LeadsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLead, setSelectedLead] = useState(null);

  const getStatusBadge = (status) => {
    switch (status) {
      case "pending": return <span className={`${styles.badge} ${styles.badgePending}`}>Pending</span>;
      case "reached": return <span className={`${styles.badge} ${styles.badgeReached}`}>Reached Out</span>;
      case "replied": return <span className={`${styles.badge} ${styles.badgeReplied}`}>Replied</span>;
      default: return null;
    }
  };

  const filteredLeads = LEADS_DATA.filter(lead => 
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
          <button className={styles.filterBtn}>
            <Filter size={18} />
            Filters
          </button>
          <button className={styles.bulkBtn}>
            Bulk Actions
          </button>
        </div>
      </div>

      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Company</th>
              <th>ICP Score</th>
              <th>Niche</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredLeads.map((lead) => (
              <tr 
                key={lead.id} 
                className="animate-fade-in"
                onClick={() => setSelectedLead(lead)}
                style={{ cursor: "pointer" }}
              >
                <td>
                  <div style={{ fontWeight: 500 }}>{lead.name}</div>
                  <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>{lead.email}</div>
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
                <td>
                  <button style={{ color: "var(--text-secondary)" }}>
                    <MoreHorizontal size={20} />
                  </button>
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
                  {selectedLead.researchSummary}
                </p>
              </div>
            </div>
            
            <div className={styles.modalFooter}>
              <button className={styles.filterBtn} onClick={() => setSelectedLead(null)}>Close</button>
              <button className={styles.bulkBtn}>Generate Message</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
