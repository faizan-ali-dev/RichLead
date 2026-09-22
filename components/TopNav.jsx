"use client";

import { useState, useEffect } from "react";
import styles from "./TopNav.module.css";
import { usePathname } from "next/navigation";
import { Sun, Moon } from "lucide-react";

const routeTitles = {
  "/": "Dashboard Overview",
  "/leads": "Leads Database",
  "/review": "Review Queue",
  "/inbox": "Unified Smart Inbox",
  "/campaigns": "Campaign & AI Settings",
  "/sequences": "Multi-step Sequences",
  "/senders": "Inbox & Sender Rotation",
  "/suppression": "Global Suppression List",
  "/settings": "Settings",
};

export default function TopNav() {
  const pathname = usePathname();
  const title = routeTitles[pathname] || "Dashboard";
  
  const [isAutopilot, setIsAutopilot] = useState(false);
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  return (
    <header className={styles.topNav}>
      <h1 className={styles.title}>{title}</h1>
      
      <div className={styles.actions}>
        <button onClick={toggleTheme} className={styles.themeToggle} title="Toggle Theme">
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
