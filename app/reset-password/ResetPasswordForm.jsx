"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Lock } from "lucide-react";
import Link from "next/link";
import AuthShell from "@/components/AuthShell";
import styles from "@/components/AuthShell.module.css";
import { API_BASE } from "../lib/api";

export default function ResetPasswordForm({ uid, token }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/users/password-reset/confirm/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid, token, new_password: password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(Object.values(data).flat().join(" ") || "This reset link is invalid or expired.");
        return;
      }
      setSuccess(true);
    } catch {
      setError("Network error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const validLink = uid && token;

  return (
    <AuthShell quote="A secure reset keeps your next conversation yours.">
      <h1 className={styles.title}>Set a new password</h1>
      <p className={styles.subtitle}>Choose a strong password you haven’t used before.</p>

      {success ? (
        <div className={`${styles.message} ${styles.success}`} role="status">
          Your password has been updated. You can now sign in.
        </div>
      ) : !validLink ? (
        <div className={styles.message} role="alert">
          This reset link is missing or invalid. Request a new one to continue.
        </div>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit}>
          {error && <div className={styles.message} role="alert">{error}</div>}
          <div className={styles.field}>
            <label className={styles.label} htmlFor="new-password">New password</label>
            <div className={styles.inputWrap}>
              <Lock className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="new-password"
                name="new-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Create a strong password"
                minLength={8}
                required
              />
            </div>
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="confirm-password">Confirm password</label>
            <div className={styles.inputWrap}>
              <Lock className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="confirm-password"
                name="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Enter the password again"
                minLength={8}
                required
              />
            </div>
          </div>
          <button className={styles.primaryButton} type="submit" disabled={isLoading}>
            {isLoading ? "Updating password…" : <>Update password <ArrowRight size={18} /></>}
          </button>
        </form>
      )}

      <Link className={styles.textLink} href="/login"><ArrowLeft size={16} /> Back to sign in</Link>
    </AuthShell>
  );
}
