"use client";

import styles from "./TopNav.module.css";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LogOut, Moon, Sun, UserRound } from "lucide-react";
import { API_BASE, authFetch, clearTokens, getAccessToken } from "@/app/lib/api";
import useAutopilotSetting from "./useAutopilotSetting";

const routeTitles = {
  "/": "Dashboard Overview",
  "/leads": "Leads Database",
  "/review": "Review Queue",
  "/inbox": "Unified Smart Inbox",
  "/campaigns": "Campaign & AI Settings",
  "/senders": "Inbox & Sender Rotation",
  "/suppression": "Global Suppression List",
  "/settings": "Settings",
  "/settings/autopilot": "Autopilot Settings",
  "/settings/business": "Business Profile",
  "/settings/ai": "AI Provider",
  "/settings/prompts": "Prompt Settings",
  "/settings/follow-ups": "Follow-up Settings",
  "/settings/integrations": "API Integrations",
  "/settings/webhooks": "CRM Webhooks",
  "/settings/profile": "Account Profile",
};

export default function TopNav({ theme = "dark", themePreference = "system", onToggleTheme }) {
  const pathname = usePathname();
  const router = useRouter();
  const title = routeTitles[pathname] || "Dashboard";
  const [profileOpen, setProfileOpen] = useState(false);
  const [profile, setProfile] = useState(null);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const profileMenuRef = useRef(null);
  
  const { autopilot, updateAutopilot, isLoading, isSaving, error } = useAutopilotSetting();

  useEffect(() => {
    if (!profileOpen) return;
    let active = true;
    authFetch("/api/users/settings/")
      .then(async (response) => {
        if (!response.ok) return;
        const data = await response.json();
        if (active) setProfile(data);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [profileOpen]);

  useEffect(() => {
    if (!profileOpen) return;
    const closeOnOutsideClick = (event) => {
      if (!profileMenuRef.current?.contains(event.target)) setProfileOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setProfileOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [profileOpen]);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    const refresh = typeof window === "undefined" ? null : localStorage.getItem("richlead_refresh");
    try {
      if (refresh) {
        await fetch(`${API_BASE}/api/token/blacklist/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
        });
      }
    } catch (_) {
      // Local credentials are still cleared if the server cannot be reached.
    } finally {
      clearTokens();
      router.replace("/login");
    }
  };

  const profileInitial = (profile?.username || profile?.email || "A").trim().charAt(0).toUpperCase() || "A";
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
          <span className={`${styles.toggleLabel} ${autopilot ? styles.active : ""}`}>
            Autopilot Mode
          </span>
          <label className={styles.toggle}>
            <input 
              type="checkbox" 
              checked={autopilot}
              disabled={isLoading || isSaving}
              onChange={(event) => updateAutopilot(event.target.checked)}
              aria-label="Enable Autopilot Mode"
              aria-describedby={error ? "autopilot-save-error" : undefined}
              title={error || (isSaving ? "Saving Autopilot setting…" : "")}
            />
            <span className={styles.slider}></span>
          </label>
          {error && <span id="autopilot-save-error" role="alert" className={styles.visuallyHidden}>{error}</span>}
        </div>
        
        <div className={styles.profileMenu} ref={profileMenuRef}>
          <button
            type="button"
            className={styles.profile}
            onClick={() => setProfileOpen((open) => !open)}
            aria-label="Open profile menu"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
          >
            {profileInitial}
          </button>
          {profileOpen && (
            <div className={styles.profileDropdown} role="menu" aria-label="Profile menu">
              <div className={styles.profileSummary}>
                <span className={styles.profileName}>{profile?.username || "Your account"}</span>
                <span className={styles.profileEmail}>{profile?.email || (getAccessToken() ? "Loading account…" : "Not signed in")}</span>
              </div>
              <Link href="/settings/profile" role="menuitem" className={styles.profileMenuItem} onClick={() => setProfileOpen(false)}>
                <UserRound size={16} /> Profile settings
              </Link>
              <button type="button" role="menuitem" className={styles.profileMenuItem} onClick={handleSignOut} disabled={isSigningOut}>
                <LogOut size={16} /> {isSigningOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
