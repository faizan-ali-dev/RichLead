"use client";

import styles from "./page.module.css";
import StatCard from "@/components/StatCard";
import { Users, Send, MessageSquare, Target, Activity } from "lucide-react";

export default function Home() {
  const activities = [
    { id: 1, title: "Fetched 150 leads from Apollo API (SaaS Founders in NY)", time: "10 mins ago", icon: Target },
    { id: 2, title: "LLM generated 45 custom messages for review", time: "25 mins ago", icon: MessageSquare },
    { id: 3, title: "Sent out 12 approved emails", time: "1 hour ago", icon: Send },
    { id: 4, title: "New reply received from 'John Doe'", time: "2 hours ago", icon: Users },
  ];

  return (
    <div className={styles.dashboard}>
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Overview</h2>
        <div className={styles.statsGrid}>
          <StatCard 
            title="Total Leads Found" 
            value="12,450" 
            icon={Target} 
            trend="up" 
            trendValue="12%" 
          />
          <StatCard 
            title="Messages Sent" 
            value="8,234" 
            icon={Send} 
            trend="up" 
            trendValue="5%" 
          />
          <StatCard 
            title="Pending Review" 
            value="45" 
            icon={MessageSquare} 
          />
          <StatCard 
            title="Reply Rate" 
            value="14.2%" 
            icon={Users} 
            trend="up" 
            trendValue="2.1%" 
          />
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
