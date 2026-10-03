"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { API_BASE } from "@/app/lib/api";

const SESSION_KEY = "richlead_analytics_session";

function getSessionId() {
  let sessionId = window.sessionStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = window.crypto?.randomUUID?.() || "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const random = Math.floor(Math.random() * 16);
      return (character === "x" ? random : (random & 0x3) | 0x8).toString(16);
    });
    window.sessionStorage.setItem(SESSION_KEY, sessionId);
  }
  return sessionId;
}

function sendEvent(eventType, path, label = "") {
  try {
    const payload = JSON.stringify({
      event_type: eventType,
      path,
      session_id: getSessionId(),
      ...(label ? { label } : {}),
    });
    void fetch(`${API_BASE}/api/admin-dashboard/track/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "omit",
      keepalive: true,
      body: payload,
    }).catch(() => {});
  } catch {
    // Analytics are optional and never interrupt navigation.
  }
}

export default function AnalyticsTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname || pathname === "/admin-dashboard") return;
    sendEvent("page_view", pathname);
  }, [pathname]);

  useEffect(() => {
    const recordCta = (event) => {
      if (window.location.pathname !== "/") return;
      const target = event.target instanceof Element ? event.target.closest("[data-analytics-label]") : null;
      const label = target?.getAttribute("data-analytics-label");
      if (label && /^[A-Za-z0-9_-]{1,64}$/.test(label)) {
        sendEvent("cta_click", window.location.pathname, label);
      }
    };
    document.addEventListener("click", recordCta);
    return () => document.removeEventListener("click", recordCta);
  }, []);

  return null;
}
