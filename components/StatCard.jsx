"use client";

import styles from "./StatCard.module.css";
import { TrendingUp, TrendingDown } from "lucide-react";

export default function StatCard({ title, value, icon: Icon, trend, trendValue }) {
  const isPositive = trend === "up";

  return (
    <div className={`${styles.card} animate-fade-in`}>
      <div className={styles.header}>
        <span>{title}</span>
        {Icon && (
          <div className={styles.icon}>
            <Icon size={20} />
          </div>
        )}
      </div>
      
      <div className={styles.value}>{value}</div>
      
      {trend && (
        <div className={`${styles.trend} ${isPositive ? styles.positive : styles.negative}`}>
          {isPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          <span>{trendValue} vs last week</span>
        </div>
      )}
    </div>
  );
}
