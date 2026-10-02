"use client";

import { useEffect, useState } from "react";
import SettingsModule from "@/components/SettingsModule";
import { authFetch } from "@/app/lib/api";
import styles from "../page.module.css";

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.full_name?.[0] || data.nickname?.[0] || data.new_email?.[0];
    throw new Error(detail || "The request could not be completed.");
  }
  return data;
}

export default function ProfileSettingsPage() {
  const [profile, setProfile] = useState(null);
  const [fullName, setFullName] = useState("");
  const [nickname, setNickname] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [loadingError, setLoadingError] = useState("");
  const [profileMessage, setProfileMessage] = useState(null);
  const [emailMessage, setEmailMessage] = useState(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isRequestingEmailChange, setIsRequestingEmailChange] = useState(false);
  const [isConfirmingEmailChange, setIsConfirmingEmailChange] = useState(false);

  useEffect(() => {
    let active = true;
    authFetch("/api/users/settings/")
      .then(async (response) => {
        const data = await readResponse(response);
        if (!active) return;
        setProfile(data);
        setFullName(data.full_name || "");
        setNickname(data.nickname || "");
        setNewEmail(data.pending_email || "");
        if (data.pending_email) {
          setEmailMessage({
            type: "success",
            text: `A verification code is pending for ${data.pending_email}. Enter it below to finish changing your email.`,
          });
        }
      })
      .catch((error) => {
        if (active) setLoadingError(error.message || "Could not load your account profile.");
      });
    return () => { active = false; };
  }, []);

  const saveProfile = async (event) => {
    event.preventDefault();
    setIsSavingProfile(true);
    setProfileMessage(null);
    try {
      const response = await authFetch("/api/users/profile/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName, nickname }),
      });
      const data = await readResponse(response);
      setProfile((current) => ({ ...current, ...data }));
      setFullName(data.full_name);
      setNickname(data.nickname || "");
      setProfileMessage({ type: "success", text: "Your profile has been saved." });
      window.dispatchEvent(new Event("richlead-profile-updated"));
    } catch (error) {
      setProfileMessage({ type: "error", text: error.message || "Could not save your profile." });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const requestEmailChange = async (event) => {
    event.preventDefault();
    setIsRequestingEmailChange(true);
    setEmailMessage(null);
    try {
      const response = await authFetch("/api/users/profile/email-change/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_email: newEmail }),
      });
      const data = await readResponse(response);
      setNewEmail(data.pending_email);
      setVerificationCode("");
      setProfile((current) => ({ ...current, pending_email: data.pending_email }));
      setEmailMessage({ type: "success", text: data.detail });
    } catch (error) {
      setEmailMessage({ type: "error", text: error.message || "Could not send a verification code." });
    } finally {
      setIsRequestingEmailChange(false);
    }
  };

  const confirmEmailChange = async (event) => {
    event.preventDefault();
    setIsConfirmingEmailChange(true);
    setEmailMessage(null);
    try {
      const response = await authFetch("/api/users/profile/email-change/confirm/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: verificationCode }),
      });
      const data = await readResponse(response);
      setProfile((current) => ({ ...current, email: data.email, pending_email: "" }));
      setNewEmail("");
      setVerificationCode("");
      setEmailMessage({ type: "success", text: data.detail });
    } catch (error) {
      setEmailMessage({ type: "error", text: error.message || "Could not verify the new email." });
    } finally {
      setIsConfirmingEmailChange(false);
    }
  };

  return (
    <SettingsModule title="Account profile" description="Manage the name and email used for your RichLead account.">
      {loadingError ? <p role="alert" className={styles.errorBox}>{loadingError}</p> : !profile ? <p className={styles.hint}>Loading account details…</p> : (
        <>
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Profile details</h2>
            <form onSubmit={saveProfile}>
              <div className={styles.formGroup}>
                <label htmlFor="profile-full-name">Full name</label>
                <input
                  id="profile-full-name"
                  className={styles.input}
                  autoComplete="name"
                  maxLength={150}
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  required
                />
              </div>
              <div className={styles.formGroup}>
                <label htmlFor="profile-nickname">Nickname</label>
                <input
                  id="profile-nickname"
                  className={styles.input}
                  autoComplete="nickname"
                  maxLength={80}
                  value={nickname}
                  onChange={(event) => setNickname(event.target.value)}
                  placeholder="What should we call you?"
                />
              </div>
              {profileMessage && (
                <p role={profileMessage.type === "error" ? "alert" : "status"} className={profileMessage.type === "error" ? styles.errorBox : styles.successBox}>
                  {profileMessage.text}
                </p>
              )}
              <button className={styles.saveBtn} type="submit" disabled={isSavingProfile}>
                {isSavingProfile ? "Saving…" : "Save profile"}
              </button>
            </form>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Email address</h2>
            <div className={styles.formGroup}>
              <label htmlFor="profile-current-email">Current email</label>
              <input id="profile-current-email" className={styles.input} value={profile.email || ""} readOnly />
            </div>
            <p className={styles.hint}>
              To change it, we’ll send a code to the new address and a security notice to your current address. Your login email changes only after the code is verified.
            </p>
            <form onSubmit={requestEmailChange}>
              <div className={styles.formGroup}>
                <label htmlFor="profile-new-email">New email</label>
                <input
                  id="profile-new-email"
                  className={styles.input}
                  type="email"
                  autoComplete="email"
                  maxLength={254}
                  value={newEmail}
                  onChange={(event) => setNewEmail(event.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </div>
              <button className={styles.saveBtn} type="submit" disabled={isRequestingEmailChange || !newEmail.trim()}>
                {isRequestingEmailChange ? "Sending code…" : profile.pending_email ? "Resend verification code" : "Send verification code"}
              </button>
            </form>

            {profile.pending_email && (
              <form onSubmit={confirmEmailChange} className={styles.emailCodeForm}>
                <div className={styles.formGroup}>
                  <label htmlFor="profile-email-code">Verification code sent to {profile.pending_email}</label>
                  <input
                    id="profile-email-code"
                    className={styles.input}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]{6}"
                    minLength={6}
                    maxLength={6}
                    value={verificationCode}
                    onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="6-digit code"
                    required
                  />
                </div>
                <button className={styles.saveBtn} type="submit" disabled={isConfirmingEmailChange || verificationCode.length !== 6}>
                  {isConfirmingEmailChange ? "Verifying…" : "Verify and change email"}
                </button>
              </form>
            )}
            {emailMessage && (
              <p role={emailMessage.type === "error" ? "alert" : "status"} className={emailMessage.type === "error" ? styles.errorBox : styles.successBox}>
                {emailMessage.text}
              </p>
            )}
          </section>
        </>
      )}
    </SettingsModule>
  );
}
