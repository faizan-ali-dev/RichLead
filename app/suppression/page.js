"use client";

import styles from "./page.module.css";
import { ShieldAlert, Plus, Trash2, Globe } from "lucide-react";
import { useState } from "react";

const INITIAL_BLACKLIST = [
  { id: 1, value: "competitor.com", type: "Domain", addedAt: "Oct 12, 2026" },
  { id: 2, value: "ex-client@gmail.com", type: "Email", addedAt: "Oct 15, 2026" },
  { id: 3, value: "badcompany.io", type: "Domain", addedAt: "Nov 02, 2026" },
];

export default function SuppressionPage() {
  const [list, setList] = useState(INITIAL_BLACKLIST);
  const [inputValue, setInputValue] = useState("");

  const handleAdd = () => {
    if (!inputValue.trim()) return;
    
    // Simple mock logic for splitting by new lines and detecting type
    const newItems = inputValue.split('\n').filter(val => val.trim()).map((val, index) => ({
      id: Date.now() + index,
      value: val.trim(),
      type: val.includes('@') ? "Email" : "Domain",
      addedAt: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    }));

    setList([...newItems, ...list]);
    setInputValue("");
  };

  const handleDelete = (id) => {
    setList(list.filter(item => item.id !== id));
  };

  return (
    <div className={styles.page}>
      <div className={`${styles.column} animate-fade-in`}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <ShieldAlert size={20} className="text-accent-danger" />
              Add to Global Blacklist
            </h2>
            <p className={styles.cardSubtitle}>
              Paste emails or domains separated by new lines. The system will skip these during bulk Apollo fetches and outreach.
            </p>
          </div>
          
          <textarea 
            className={styles.textarea}
            placeholder="example.com&#10;john@doe.com&#10;competitor.net"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
          />

          <div className={styles.btnGroup}>
            <button className={styles.addBtn} onClick={handleAdd}>
              <Plus size={18} />
              Add to Suppression List
            </button>
          </div>
        </div>
      </div>

      <div className={`${styles.column} animate-fade-in`} style={{ animationDelay: "0.1s" }}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <Globe size={20} className="text-accent-primary" />
              Active Blacklist ({list.length})
            </h2>
          </div>

          <div className={styles.tableContainer}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Value</th>
                  <th>Type</th>
                  <th>Date Added</th>
                  <th style={{ width: '50px' }}></th>
                </tr>
              </thead>
              <tbody>
                {list.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 500 }}>{item.value}</td>
                    <td><span className={styles.badge}>{item.type}</span></td>
                    <td style={{ color: "var(--text-secondary)" }}>{item.addedAt}</td>
                    <td>
                      <button className={styles.deleteBtn} onClick={() => handleDelete(item.id)}>
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                {list.length === 0 && (
                  <tr>
                    <td colSpan="4" style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                      No items in blacklist.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
