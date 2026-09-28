"use client";

import { useState } from "react";
import { ArrowRight, Lock, Mail, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell from "@/components/AuthShell";
import styles from "@/components/AuthShell.module.css";
import { API_BASE } from "../lib/api";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [verificationPending, setVerificationPending] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationNotice, setVerificationNotice] = useState("");
  const [isResending, setIsResending] = useState(false);
  const router = useRouter();

  const handleRegister = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/api/users/register/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName, email, password }),
      });
      const data = await response.json();

      if (response.ok) {
        setVerificationPending(true);
        setVerificationNotice(data.detail || "Check your email for the verification code.");
      } else {
        setError(Object.values(data).flat().join(" ") || "Registration failed.");
      }
    } catch {
      setError("Network error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/api/users/verify-email/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code: verificationCode }),
      });
      const data = await response.json();
      if (response.ok) {
        setSuccess(true);
        setTimeout(() => router.push("/login"), 2000);
      } else {
        setError(data.detail || Object.values(data).flat().join(" ") || "Verification failed.");
      }
    } catch {
      setError("Network error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    setIsResending(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/users/verify-email/resend/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: email }),
      });
      const data = await response.json();
      setVerificationNotice(data.detail || "If verification is needed, a new code has been sent.");
    } catch {
      setError("Network error occurred.");
    } finally {
      setIsResending(false);
    }
  };

  return (
    <AuthShell quote="Good outreach begins with knowing the person behind the inbox.">
      <h1 className={styles.title}>Create your account</h1>
      <p className={styles.subtitle}>Start building better conversations with Rich Lead.</p>

      {success ? (
        <div className={`${styles.message} ${styles.success}`} role="status">
          Email verified. Redirecting to sign in…
        </div>
      ) : verificationPending ? (
        <form className={styles.form} onSubmit={handleVerify}>
          <div className={`${styles.message} ${styles.success}`} role="status">{verificationNotice}</div>
          {error && <div className={styles.message} role="alert">{error}</div>}
          <div className={styles.field}>
            <label className={styles.label} htmlFor="verification-code">Email verification code</label>
            <div className={styles.inputWrap}>
              <Mail className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="verification-code"
                name="verification-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                value={verificationCode}
                onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="Enter the 6-digit code"
                required
              />
            </div>
          </div>
          <button className={styles.primaryButton} type="submit" disabled={isLoading || verificationCode.length !== 6}>
            {isLoading ? "Verifying…" : <>Verify email <ArrowRight size={18} /></>}
          </button>
          <button className={styles.textLink} type="button" onClick={handleResend} disabled={isResending}>
            {isResending ? "Sending…" : "Resend verification code"}
          </button>
        </form>
      ) : (
        <form className={styles.form} onSubmit={handleRegister}>
          {error && <div className={styles.message} role="alert">{error}</div>}

          <div className={styles.field}>
            <label className={styles.label} htmlFor="full-name">Full name</label>
            <div className={styles.inputWrap}>
              <UserRound className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="full-name"
                name="name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Your full name"
                maxLength={150}
                required
              />
            </div>
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="email">Email</label>
            <div className={styles.inputWrap}>
              <Mail className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="email"
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

          <div className={styles.field}>
            <label className={styles.label} htmlFor="password">Password</label>
            <div className={styles.inputWrap}>
              <Lock className={styles.inputIcon} size={18} aria-hidden="true" />
              <input
                className={styles.input}
                id="password"
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

          <button className={styles.primaryButton} type="submit" disabled={isLoading}>
            {isLoading ? "Creating account…" : <>Sign up <ArrowRight size={18} /></>}
          </button>
        </form>
      )}

      <p className={styles.footer}>
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
