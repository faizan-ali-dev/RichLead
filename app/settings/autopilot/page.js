"use client";

import { Zap } from "lucide-react";
import SettingsModule from "@/components/SettingsModule";
import useAutopilotSetting from "@/components/useAutopilotSetting";
import styles from "../page.module.css";

export default function AutopilotSettingsPage() {
  const { autopilot, updateAutopilot, isLoading, isSaving, error } = useAutopilotSetting();

  return (
    <SettingsModule
      title="Autopilot"
      description="Choose whether qualified leads can be emailed automatically or should wait for manual review."
    >
      <section className={styles.section}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
          <h3 className={styles.sectionTitle} style={{ marginBottom: 0 }}>
            <Zap size={20} className="text-accent-primary" /> Autopilot mode
          </h3>
          <label style={{ display: "flex", alignItems: "center", gap: "0.65rem", cursor: isSaving ? "wait" : "pointer" }}>
            <span style={{ color: autopilot ? "var(--accent-success)" : "var(--text-secondary)" }}>
              {isLoading ? "Loading…" : isSaving ? "Saving…" : autopilot ? "Active" : "Paused"}
            </span>
            <input
              type="checkbox"
              checked={autopilot}
              disabled={isLoading || isSaving}
              onChange={(event) => updateAutopilot(event.target.checked)}
              aria-label="Enable Autopilot"
            />
          </label>
        </div>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: "1rem" }}>
          When active, RichLead can generate and send emails to leads without manual review.
          When paused, generated messages stay in the review queue.
        </p>
        {error && <p role="alert" style={{ color: "var(--accent-danger)", fontSize: "0.875rem" }}>{error}</p>}
      </section>
    </SettingsModule>
  );
}
