"use client";

import styles from "./page.module.css";
import StatCard from "@/components/StatCard";
import { Users, Send, MessageSquare, Target, Activity, Sparkles } from "lucide-react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useState, useEffect } from "react";

const chartData = [
  { name: 'Mon', sent: 400, replies: 24, bounces: 12 },
  { name: 'Tue', sent: 300, replies: 13, bounces: 8 },
  { name: 'Wed', sent: 550, replies: 45, bounces: 15 },
  { name: 'Thu', sent: 450, replies: 38, bounces: 10 },
  { name: 'Fri', sent: 600, replies: 55, bounces: 18 },
  { name: 'Sat', sent: 200, replies: 10, bounces: 5 },
  { name: 'Sun', sent: 150, replies: 5, bounces: 3 },
];

export default function Home() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      const storedToken = localStorage.getItem("richlead_token");
      if (!storedToken) {
        window.location.href = "/login";
        return;
      }

      try {
        const response = await fetch("http://127.0.0.1:8000/api/dashboard/stats/", {
          headers: { Authorization: `Bearer ${storedToken}` }
        });
        
        if (response.status === 401) {
          localStorage.removeItem("richlead_token");
          window.location.href = "/login";
          return;
        }
        
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error("Error fetching stats:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  const activities = [
    { id: 1, title: "250 leads discovered in Apollo API", time: "10 mins ago", icon: Target },
    { id: 2, title: "142 leads qualified (ICP Score > 80)", time: "25 mins ago", icon: Sparkles },
    { id: 3, title: "86 leads researched for intent signals", time: "1 hour ago", icon: Activity },
    { id: 4, title: "65 personalized messages generated", time: "2 hours ago", icon: MessageSquare },
    { id: 5, title: "12 positive replies received", time: "3 hours ago", icon: Users },
  ];

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
            <div style={{ width: '100%', height: 250 }}>
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-border)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--bg-border)', borderRadius: '8px' }}
                    itemStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Line type="monotone" dataKey="sent" stroke="var(--accent-primary)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className={`${styles.activityFeed} animate-fade-in`} style={{ animationDelay: '0.1s' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 500, marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>Response Breakdown</h3>
            <div style={{ width: '100%', height: 250 }}>
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-border)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--bg-border)', borderRadius: '8px' }}
                    itemStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Bar dataKey="replies" fill="var(--accent-success)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="bounces" fill="var(--accent-danger)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Recent Activity</h2>
        <div className={styles.activityFeed}>
          {activities.map((item, index) => {
            const Icon = item.icon;
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
                  <div className={styles.activityTime}>{item.time}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
