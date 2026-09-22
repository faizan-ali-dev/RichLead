"use client";

import styles from "./page.module.css";
import { Plus, MoreHorizontal, Mail } from "lucide-react";

const SENDERS_DATA = [
  { id: 1, email: "john@richlead.com", provider: "Google Workspace", dailyLimit: 40, sentToday: 12, status: "active" },
  { id: 2, email: "hello@richlead.net", provider: "Outlook", dailyLimit: 20, sentToday: 5, status: "warmup" },
  { id: 3, email: "sales@richlead.io", provider: "Google Workspace", dailyLimit: 40, sentToday: 40, status: "paused" },
];

export default function SendersPage() {
  const getStatusBadge = (status) => {
    switch (status) {
      case "active": return <span className={`${styles.badge} ${styles.badgeActive}`}>Active</span>;
      case "warmup": return <span className={`${styles.badge} ${styles.badgeWarmup}`}>Warming Up</span>;
      case "paused": return <span className={`${styles.badge} ${styles.badgePaused}`}>Limit Reached</span>;
      default: return null;
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.controls}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Sender Accounts</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Manage your inboxes for automated rotation and outreach.</p>
        </div>
        <button className={styles.addBtn}>
          <Plus size={18} />
          Connect Inbox
        </button>
      </div>

      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Account</th>
              <th>Provider</th>
              <th>Daily Limit</th>
              <th>Sent Today</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {SENDERS_DATA.map((sender) => (
              <tr key={sender.id} className="animate-fade-in">
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Mail size={16} color="var(--text-secondary)" />
                    <span style={{ fontWeight: 500 }}>{sender.email}</span>
                  </div>
                </td>
                <td>{sender.provider}</td>
                <td>{sender.dailyLimit}</td>
                <td>
                  <span style={{ color: sender.sentToday >= sender.dailyLimit ? 'var(--accent-danger)' : 'var(--text-primary)' }}>
                    {sender.sentToday}
                  </span>
                </td>
                <td>{getStatusBadge(sender.status)}</td>
                <td>
                  <button style={{ color: "var(--text-secondary)", cursor: 'pointer' }}>
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
