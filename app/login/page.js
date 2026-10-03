"use client";

import { useState } from "react";
import { ArrowRight, Eye, EyeOff, Lock, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell from "@/components/AuthShell";
import styles from "@/components/AuthShell.module.css";
import { API_BASE, storeTokens } from "../lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [canResendVerification, setCanResendVerification] = useState(false);
  const [resendNotice, setResendNotice] = useState("");
  const [isResending, setIsResending] = useState(false);
  const router = useRouter();

  const handleLogin = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    setCanResendVerification(false);
    setResendNotice("");

    try {
      const response = await fetch(API_BASE + "/api/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();

      if (response.ok) {
        storeTokens({ access: data.access, refresh: data.refresh });
        router.push("/dashboard");
      } else {
        setError(data.detail || "Invalid credentials");
        setCanResendVerification(String(data.detail || "").toLowerCase().includes("verify"));
      }
    } catch {
      setError("We could not reach RichLead. Check your connection and try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setIsResending(true);
    setResendNotice("");
    try {
      const response = await fetch(API_BASE + "/api/users/verify-email/resend/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: username }),
      });
      const data = await response.json();
      setResendNotice(data.detail || "If verification is needed, a new code has been sent.");
    } catch {
      setResendNotice("We could not reach RichLead. Try again in a moment.");
    } finally {
      setIsResending(false);
    }
  };

  return (
    <AuthShell quote="Build a stronger pipeline with thoughtful outreach and conversations that move forward.">
      <div className={styles.authIntro}>
        <p className={styles.eyebrow}>YOUR WORKSPACE</p>
        <h1 className={styles.title}>Welcome back</h1>
        <p className={styles.subtitle}>Sign in to pick up where your outreach left off.</p>
      </div>

      {error && <div className={styles.message} role="alert">{error}</div>}
      {canResendVerification && (
        <div className={styles.resendBlock}>
          <button className={styles.textLink} type="button" onClick={handleResendVerification} disabled={isResending}>
            {isResending ? "Sending code…" : "Resend verification code"}
          </button>
          {resendNotice && <p className={styles.notice} role="status">{resendNotice}</p>}
        </div>
      )}

      <form className={styles.form} onSubmit={handleLogin}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="login-identifier">Email or username</label>
          <div className={styles.inputWrap}>
            <Mail className={styles.inputIcon} size={18} aria-hidden="true" />
            <input
              className={styles.input}
              id="login-identifier"
              name="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="you@company.com"
              required
            />
          </div>
        </div>

        <div className={styles.field}>
          <div className={styles.labelRow}>
            <label className={styles.label} htmlFor="login-password">Password</label>
            <Link className={styles.inlineLink} href="/forgot-password">Forgot password?</Link>
          </div>
          <div className={styles.inputWrap}>
            <Lock className={styles.inputIcon} size={18} aria-hidden="true" />
            <input
              className={styles.input}
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              required
            />
            <button
              className={styles.passwordToggle}
              type="button"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        <button className={styles.primaryButton} type="submit" disabled={isLoading}>
          {isLoading ? "Signing in…" : <>Sign in <ArrowRight size={18} /></>}
        </button>
      </form>

      <p className={styles.footer}>
        New to RichLead? <Link href="/register">Create an account</Link>
      </p>
    </AuthShell>
  );
}
