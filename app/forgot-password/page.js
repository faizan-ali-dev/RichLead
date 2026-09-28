"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Mail } from "lucide-react";
import Link from "next/link";
import AuthShell from "@/components/AuthShell";
import styles from "@/components/AuthShell.module.css";
import { API_BASE } from "../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/api/users/password-reset/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || "Password reset email is not available right now.");
        return;
      }
      setSent(true);
    } catch {
      setError("Network error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell quote="A fresh start is only a secure reset away.">
      <h1 className={styles.title}>Forgot your password?</h1>
      <p className={styles.subtitle}>Enter the email address on your account and we’ll send a reset link.</p>

      {sent ? (
        <div className={`${styles.message} ${styles.success}`} role="status">
          If an account uses that email, a password reset link has been sent. Check your inbox and spam folder.
        </div>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit}>
          {error && <div className={styles.message} role="alert">{error}</div>}
          <div className={styles.field}>
            <label className={styles.label} htmlFor="reset-email">Email</label>
            <div className={styles.inputWrap}>
              <Mail className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="reset-email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@company.com"
                required
              />
            </div>
          </div>
          <button className={styles.primaryButton} type="submit" disabled={isLoading}>
            {isLoading ? "Sending link…" : <>Send reset link <ArrowRight size={18} /></>}
          </button>
        </form>
      )}

      <Link className={styles.textLink} href="/login"><ArrowLeft size={16} /> Back to sign in</Link>
    </AuthShell>
  );
}
