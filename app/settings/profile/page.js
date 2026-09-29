"use client";

import { useEffect, useState } from "react";
import SettingsModule from "@/components/SettingsModule";
import { authFetch } from "@/app/lib/api";
import styles from "../page.module.css";

export default function ProfileSettingsPage() {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    authFetch("/api/users/settings/")
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load your account profile.");
        const data = await response.json();
        if (active) setProfile(data);
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || "Could not load your account profile.");
      });
    return () => { active = false; };
  }, []);

  return (
    <SettingsModule title="Account profile" description="Your current RichLead account identity.">
      <section className={styles.section}>
        {error ? <p role="alert" className={styles.errorBox}>{error}</p> : !profile ? <p className={styles.hint}>Loading account details…</p> : (
          <>
            <div className={styles.formGroup}>
              <label>Username</label>
              <input className={styles.input} value={profile.username || ""} readOnly />
            </div>
            <div className={styles.formGroup}>
              <label>Email address</label>
              <input className={styles.input} value={profile.email || ""} readOnly />
            </div>
            <p className={styles.hint}>Profile editing is not available yet. These values are read from your signed-in account.</p>
          </>
        )}
      </section>
    </SettingsModule>
  );
}
