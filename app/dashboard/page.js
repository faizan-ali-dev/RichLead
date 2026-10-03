"use client";

import { API_BASE, clearTokens } from "../lib/api";

import styles from "./page.module.css";
import StatCard from "@/components/StatCard";
import { Users, Send, Mail, MessageSquare, Target, Activity, Sparkles } from "lucide-react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const activityIcons = {
  lead: Target,
  sent: Send,
  reply: Users,
  inbound: Mail,
  research: Sparkles,
  bounce: Activity,
};

function formatTimeAgo(value) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";

  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export default function Home() {
  const router = useRouter();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const fetchStats = async () => {
      const storedToken = localStorage.getItem("richlead_token");
      if (!storedToken) {
        router.push("/login");
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/api/dashboard/stats/`, {
          headers: { Authorization: `Bearer ${storedToken}` }
        });
        
        if (response.status === 401) {
          clearTokens();
          router.push("/login");
          return;
        }
        
        if (!response.ok) throw new Error("Dashboard request failed");
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error("Error fetching stats:", error);
        setLoadError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, [router]);

  const chartData = stats?.analytics ?? [];
  const activities = stats?.recent_activity ?? [];
  const hasChartActivity = chartData.some((day) => day.sent || day.replies || day.bounces);

  return (
    <div className={styles.dashboard}>
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Overview</h2>
        <div className={styles.statsGrid}>
          <StatCard 
            title="Leads Discovered" 
            value={stats ? stats.leads_discovered : "..."} 
            icon={Target} 
            trend="up" 
            trendValue="12%" 
          />
          <StatCard 
            title="Qualified (ICP >80)" 
            value={stats ? stats.qualified : "..."} 
            icon={Sparkles} 
            trend="up" 
            trendValue="8%" 
          />
          <StatCard 
            title="AI Researched" 
            value={stats ? stats.ai_researched : "..."} 
            icon={Activity} 
            trend="up" 
            trendValue="15%" 
          />
          <StatCard 
            title="Messages Generated" 
            value={stats ? stats.messages_generated : "..."} 
            icon={MessageSquare} 
            trend="up" 
            trendValue="20%" 
          />
          <StatCard 
            title="Pending Review" 
            value={stats ? stats.pending_review : "..."} 
            icon={MessageSquare} 
          />
          <StatCard 
            title="Reply Rate" 
            value={stats ? stats.reply_rate : "..."} 
            icon={Users} 
            trend="up" 
            trendValue="2.1%" 
          />
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Campaign Analytics</h2>
        <div className={styles.chartsGrid}>
          <div className={`${styles.activityFeed} animate-fade-in`}>
            <h3 style={{ fontSize: '1rem', fontWeight: 500, marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>Outreach Volume (Last 7 Days)</h3>
            {loading ? <p>Loading outreach data…</p> : loadError ? <p>Analytics are temporarily unavailable.</p> : !hasChartActivity ? <p>No email activity in the last 7 days.</p> : (
              <div style={{ width: '100%', height: 250 }}>
                <ResponsiveContainer>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-border)" />
                    <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                    <YAxis stroke="var(--text-muted)" fontSize={12} allowDecimals={false} />
                    <Tooltip
                      labelFormatter={(label, payload) => payload?.[0]?.payload?.date ? new Date(`${payload[0].payload.date}T00:00:00`).toLocaleDateString() : label}
                      contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--bg-border)', borderRadius: '8px' }}
                      itemStyle={{ color: 'var(--text-primary)' }}
                    />
                    <Line name="Emails sent" type="monotone" dataKey="sent" stroke="var(--accent-primary)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className={`${styles.activityFeed} animate-fade-in`} style={{ animationDelay: '0.1s' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 500, marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>Response Breakdown</h3>
            {loading ? <p>Loading response data…</p> : loadError ? <p>Analytics are temporarily unavailable.</p> : !hasChartActivity ? <p>No response data in the last 7 days.</p> : (
              <div style={{ width: '100%', height: 250 }}>
                <ResponsiveContainer>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-border)" />
                    <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                    <YAxis stroke="var(--text-muted)" fontSize={12} allowDecimals={false} />
                    <Tooltip
                      labelFormatter={(label, payload) => payload?.[0]?.payload?.date ? new Date(`${payload[0].payload.date}T00:00:00`).toLocaleDateString() : label}
                      contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--bg-border)', borderRadius: '8px' }}
                      itemStyle={{ color: 'var(--text-primary)' }}
                    />
                    <Legend />
                    <Bar name="Lead replies" dataKey="replies" fill="var(--accent-success)" radius={[4, 4, 0, 0]} />
                    <Bar name="Recorded bounces" dataKey="bounces" fill="var(--accent-danger)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Recent Activity</h2>
        <div className={styles.activityFeed}>
          {loading ? <p>Loading recent activity…</p> : loadError ? <p>Activity is temporarily unavailable.</p> : activities.length === 0 ? <p>No activity recorded yet.</p> : activities.map((item, index) => {
            const Icon = activityIcons[item.type] || Activity;
            return (
              <div
                key={item.id}
                className={`${styles.activityItem} animate-fade-in`}
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className={styles.activityIcon}>
                  <Icon size={18} />
                </div>
                <div className={styles.activityContent}>
                  <div className={styles.activityTitle}>{item.title}</div>
                  <div className={styles.activityTime}>{formatTimeAgo(item.occurred_at)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
