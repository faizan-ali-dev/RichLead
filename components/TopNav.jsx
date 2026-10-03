"use client";

import styles from "./TopNav.module.css";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useCallback } from "react";
import { Bell, LogOut, Moon, Sun, UserRound } from "lucide-react";
import { API_BASE, authFetch, clearTokens, getAccessToken } from "@/app/lib/api";
import useAutopilotSetting from "./useAutopilotSetting";

const routeTitles = {
  "/dashboard": "Dashboard Overview",
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
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const profileMenuRef = useRef(null);
  const notificationsMenuRef = useRef(null);
  
  const { autopilot, updateAutopilot, isLoading, isSaving, error } = useAutopilotSetting();

  const refreshNotifications = useCallback(async () => {
    if (!getAccessToken()) return;
    try {
      const response = await authFetch("/api/inbox/notifications/");
      if (!response.ok) return;
      const data = await response.json();
      setUnreadCount(data.unread_count || 0);
      setNotifications(Array.isArray(data.notifications) ? data.notifications : []);
    } catch {
      // Notifications are supplementary; keep the rest of navigation usable.
    }
  }, []);

  useEffect(() => {
    const initialRefresh = window.setTimeout(refreshNotifications, 0);
    const interval = window.setInterval(refreshNotifications, 60_000);
    window.addEventListener("richlead-inbox-updated", refreshNotifications);
    window.addEventListener("richlead-notifications-update", refreshNotifications);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
      window.removeEventListener("richlead-inbox-updated", refreshNotifications);
      window.removeEventListener("richlead-notifications-update", refreshNotifications);
    };
  }, [refreshNotifications]);

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
    if (!profileOpen && !notificationsOpen) return;
    const closeOnOutsideClick = (event) => {
      if (!profileMenuRef.current?.contains(event.target) && !notificationsMenuRef.current?.contains(event.target)) {
        setProfileOpen(false);
        setNotificationsOpen(false);
      }
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setProfileOpen(false);
        setNotificationsOpen(false);
      }
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [profileOpen, notificationsOpen]);

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

  const profileInitial = (profile?.nickname || profile?.full_name || profile?.email || "A").trim().charAt(0).toUpperCase() || "A";

  const openNotification = (leadId) => {
    setNotificationsOpen(false);
    router.push(`/inbox?lead=${encodeURIComponent(leadId)}`);
    window.setTimeout(() => {
      window.dispatchEvent(new CustomEvent("richlead-open-inbox-thread", { detail: { leadId } }));
    }, 0);
  };

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

        <div className={styles.notificationMenu} ref={notificationsMenuRef}>
          <button
            type="button"
            className={styles.notificationButton}
            onClick={() => {
              setNotificationsOpen((open) => !open);
              setProfileOpen(false);
              refreshNotifications();
            }}
            aria-label={unreadCount ? `${unreadCount} unread replies` : "Notifications"}
            aria-expanded={notificationsOpen}
            title={unreadCount ? `${unreadCount} unread replies` : "Notifications"}
          >
            <Bell size={20} />
            {unreadCount > 0 && <span className={styles.notificationBadge}>{unreadCount > 99 ? "99+" : unreadCount}</span>}
          </button>
          {notificationsOpen && (
            <div className={styles.notificationDropdown} role="dialog" aria-label="Reply notifications">
              <div className={styles.notificationHeader}>
                <span>Replies</span>
                {unreadCount > 0 && <span>{unreadCount} unread</span>}
              </div>
              <div className={styles.notificationList}>
                {notifications.length === 0 ? (
                  <div className={styles.notificationEmpty}>No new replies</div>
                ) : notifications.map((item) => (
                  <button
                    type="button"
                    key={item.lead_id}
                    className={styles.notificationItem}
                    onClick={() => openNotification(item.lead_id)}
                  >
                    <span className={styles.notificationItemTop}>
                      <strong>{item.lead_name}</strong>
                      {item.unread_count > 1 && <span className={styles.notificationCount}>{item.unread_count}</span>}
                    </span>
                    <span className={styles.notificationSubject}>{item.subject}</span>
                    <span className={styles.notificationPreview}>{item.preview || "New email reply"}</span>
                    {item.account_email && <span className={styles.notificationMailbox}>To {item.account_email}</span>}
                  </button>
                ))}
              </div>
              <button type="button" className={styles.viewInboxButton} onClick={() => { setNotificationsOpen(false); router.push("/inbox"); }}>
                Open inbox
              </button>
            </div>
          )}
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
                <span className={styles.profileName}>{profile?.nickname || profile?.full_name || "Your account"}</span>
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
