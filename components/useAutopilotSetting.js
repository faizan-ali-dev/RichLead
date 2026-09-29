"use client";

import { useCallback, useEffect, useState } from "react";
import { authFetch } from "@/app/lib/api";

const STORAGE_KEY = "richlead_autopilot_active";
const CHANGE_EVENT = "richlead-autopilot-change";

function publishAutopilot(value) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, String(value));
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: value }));
}

export default function useAutopilotSetting() {
  const [autopilot, setAutopilot] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const syncFromEvent = (event) => {
      if (typeof event.detail === "boolean") setAutopilot(event.detail);
    };
    const syncFromStorage = (event) => {
      if (event.key === STORAGE_KEY && event.newValue !== null) {
        setAutopilot(event.newValue === "true");
      }
    };

    window.addEventListener(CHANGE_EVENT, syncFromEvent);
    window.addEventListener("storage", syncFromStorage);

    let isMounted = true;
    authFetch("/api/users/settings/")
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load Autopilot setting.");
        const data = await response.json();
        if (isMounted) publishAutopilot(Boolean(data.autopilot_active));
      })
      .catch(() => {
        if (isMounted) setError("Autopilot setting could not be loaded.");
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
      window.removeEventListener(CHANGE_EVENT, syncFromEvent);
      window.removeEventListener("storage", syncFromStorage);
    };
  }, []);

  const updateAutopilot = useCallback(async (nextValue) => {
    const previousValue = autopilot;
    setAutopilot(nextValue);
    setIsSaving(true);
    setError("");

    try {
      const response = await authFetch("/api/users/settings/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ autopilot_active: nextValue }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not save Autopilot setting.");
      publishAutopilot(Boolean(data.autopilot_active));
      return true;
    } catch (saveError) {
      setAutopilot(previousValue);
      setError(saveError.message || "Could not save Autopilot setting.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [autopilot]);

  return { autopilot, updateAutopilot, isLoading, isSaving, error };
}
