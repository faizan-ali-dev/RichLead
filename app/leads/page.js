"use client";

import styles from "./page.module.css";
import { Search, Filter, MoreHorizontal } from "lucide-react";
import { useState } from "react";

const LEADS_DATA = [
  { id: 1, name: "Alice Johnson", company: "TechCorp", niche: "SaaS", status: "replied", email: "alice@techcorp.com" },
  { id: 2, name: "Bob Smith", company: "Innovate Inc", niche: "E-commerce", status: "reached", email: "bob@innovate.com" },
  { id: 3, name: "Charlie Davis", company: "Growthify", niche: "Marketing", status: "pending", email: "charlie@growthify.com" },
  { id: 4, name: "Diana Prince", company: "Amazon", niche: "Retail", status: "reached", email: "diana@amazon.com" },
  { id: 5, name: "Evan Wright", company: "Stripe", niche: "Fintech", status: "pending", email: "evan@stripe.com" },
];

export default function LeadsPage() {
  const [searchTerm, setSearchTerm] = useState("");

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
              <th>Niche</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredLeads.map((lead) => (
              <tr key={lead.id} className="animate-fade-in">
                <td>
                  <div style={{ fontWeight: 500 }}>{lead.name}</div>
                  <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>{lead.email}</div>
                </td>
                <td>{lead.company}</td>
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
    </div>
  );
}
