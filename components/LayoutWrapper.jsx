"use client";

import { useEffect, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import TopNav from "./TopNav";
import styles from "./Layout.module.css";

const THEME_STORAGE_KEY = "richlead_theme";

function getThemePreference() {
  if (typeof window === "undefined") return "system";
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return ["system", "dark", "light"].includes(saved) ? saved : "system";
}

function subscribeThemePreference(callback) {
  window.addEventListener("storage", callback);
  window.addEventListener("richlead-theme-change", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("richlead-theme-change", callback);
  };
}

function getSystemPrefersDark() {
  return typeof window === "undefined"
    ? true
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function subscribeSystemTheme(callback) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

export default function LayoutWrapper({ children }) {
  const pathname = usePathname();
  const themePreference = useSyncExternalStore(
    subscribeThemePreference,
    getThemePreference,
    () => "system",
  );
  const systemPrefersDark = useSyncExternalStore(
    subscribeSystemTheme,
    getSystemPrefersDark,
    () => true,
  );
  const isAuthPage = pathname === "/login" || pathname === "/register";
  const isStandalonePage = isAuthPage || pathname === "/terms" || pathname === "/privacy";

  const theme = themePreference === "system"
    ? (systemPrefersDark ? "dark" : "light")
    : themePreference;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const setSavedThemePreference = (nextTheme) => {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    window.dispatchEvent(new Event("richlead-theme-change"));
  };

  const toggleTheme = () => {
    const nextTheme = themePreference === "system"
      ? "dark"
      : themePreference === "dark"
        ? "light"
        : "system";
    setSavedThemePreference(nextTheme);
  };

  if (isStandalonePage) {
    return (
      <div className={styles.layout}>
        <div className={styles.mainContent} style={{ marginLeft: 0, width: '100vw' }}>
          <main className={styles.pageContent} style={{ padding: 0 }}>
            {children}
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.layout}>
      <Sidebar />
      <div className={styles.mainContent}>
        <TopNav theme={theme} themePreference={themePreference} onToggleTheme={toggleTheme} />
        <main className={styles.pageContent}>
          {children}
        </main>
      </div>
    </div>
  );
}
