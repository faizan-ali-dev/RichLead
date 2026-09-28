"use client";

import { useState } from "react";
import styles from "./TopNav.module.css";
import { usePathname } from "next/navigation";
import { Sun, Moon } from "lucide-react";

const routeTitles = {
  "/": "Dashboard Overview",
  "/leads": "Leads Database",
  "/review": "Review Queue",
  "/inbox": "Unified Smart Inbox",
  "/campaigns": "Campaign & AI Settings",
  "/senders": "Inbox & Sender Rotation",
  "/suppression": "Global Suppression List",
  "/settings": "Settings",
};

export default function TopNav({ theme = "dark", themePreference = "system", onToggleTheme }) {
  const pathname = usePathname();
  const title = routeTitles[pathname] || "Dashboard";
  
  const [isAutopilot, setIsAutopilot] = useState(false);
  return (
    <header className={styles.topNav}>
      <h1 className={styles.title}>{title}</h1>
      
      <div className={styles.actions}>
        <button
          onClick={onToggleTheme}
          className={styles.themeToggle}
          title={`Theme: ${themePreference}. Click to cycle.`}
          aria-label={`Theme preference: ${themePreference}. Click to change.`}
        >
          {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
        </button>

        <div className={styles.toggleWrapper}>
          <span className={`${styles.toggleLabel} ${isAutopilot ? styles.active : ""}`}>
            Autopilot Mode
          </span>
          <label className={styles.toggle}>
            <input 
              type="checkbox" 
              checked={isAutopilot}
              onChange={() => setIsAutopilot(!isAutopilot)}
            />
            <span className={styles.slider}></span>
          </label>
        </div>
        
        <div className={styles.profile}>
          A
        </div>
      </div>
    </header>
  );
}
