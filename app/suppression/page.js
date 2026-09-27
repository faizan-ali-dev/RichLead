"use client";

import styles from "./page.module.css";
import { ShieldAlert, Plus, Trash2, Globe } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { authFetch, asList } from "../lib/api";

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export default function SuppressionPage() {
  const [list, setList] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const loadList = useCallback(async () => {
    try {
      const res = await authFetch("/api/integrations/suppression/");
      if (!res.ok) return;
      const rows = asList(await res.json());
      setList(
        rows.map((r) => ({
          id: r.id,
          value: r.email || r.domain,
          type: r.email ? "Email" : "Domain",
          addedAt: formatDate(r.created_at),
        }))
      );
    } catch {
      setError("Could not load the suppression list.");
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleAdd = async () => {
    if (!inputValue.trim() || isSaving) return;
    setIsSaving(true);
    setError("");

    const entries = inputValue.split("\n").map((v) => v.trim()).filter(Boolean);
    const failures = [];

    for (const value of entries) {
      // An '@' means a specific address; anything else suppresses the whole domain.
      const body = value.includes("@") ? { email: value } : { domain: value };
      try {
        const res = await authFetch("/api/integrations/suppression/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...body, reason: "manual" }),
        });
        if (!res.ok) failures.push(value);
      } catch {
        failures.push(value);
      }
    }

    if (failures.length) {
      setError(`Could not add: ${failures.join(", ")}`);
    }
    setInputValue("");
    setIsSaving(false);
    await loadList();
  };

  const handleDelete = async (id) => {
    try {
      const res = await authFetch(`/api/integrations/suppression/${id}/`, { method: "DELETE" });
      if (res.ok) setList(list.filter((item) => item.id !== id));
    } catch {
      setError("Could not remove that entry.");
    }
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

          {error && (
            <p style={{ color: "var(--accent-danger)", fontSize: "0.85rem", marginTop: "0.75rem" }}>
              {error}
            </p>
          )}

          <div className={styles.btnGroup}>
            <button className={styles.addBtn} onClick={handleAdd} disabled={isSaving}>
              <Plus size={18} />
              {isSaving ? "Saving..." : "Add to Suppression List"}
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
