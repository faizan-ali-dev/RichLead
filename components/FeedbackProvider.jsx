"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import styles from "./FeedbackProvider.module.css";

const FeedbackContext = createContext(null);

const TOAST_ICONS = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertCircle,
  info: Info,
};

export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [dialog, setDialog] = useState(null);
  const nextId = useRef(0);
  const timers = useRef(new Map());
  const resolver = useRef(null);
  const cancelButton = useRef(null);
  const dialogRef = useRef(null);

  const dismiss = useCallback((id) => {
    const timer = timers.current.get(id);
    if (timer) window.clearTimeout(timer);
    timers.current.delete(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback((message, options = {}) => {
    const id = ++nextId.current;
    const type = ["success", "error", "warning", "info"].includes(options.type) ? options.type : "info";
    const toast = {
      id,
      type,
      title: options.title || ({ success: "Success", error: "Something went wrong", warning: "Attention", info: "Notice" }[type]),
      message: String(message),
    };
    setToasts((current) => [...current.slice(-3), toast]);
    const duration = Number.isFinite(options.duration) ? options.duration : 6000;
    if (duration > 0) {
      timers.current.set(id, window.setTimeout(() => dismiss(id), duration));
    }
    return id;
  }, [dismiss]);

  const confirm = useCallback((options = {}) => new Promise((resolve) => {
    if (resolver.current) resolver.current(false);
    resolver.current = resolve;
    setDialog({
      title: options.title || "Confirm action",
      message: options.message || "Are you sure you want to continue?",
      confirmLabel: options.confirmLabel || "Continue",
      cancelLabel: options.cancelLabel || "Cancel",
      variant: options.variant === "danger" ? "danger" : "primary",
    });
  }), []);

  const finishConfirm = useCallback((value) => {
    resolver.current?.(value);
    resolver.current = null;
    setDialog(null);
  }, []);

  useEffect(() => {
    if (!dialog) return undefined;
    cancelButton.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") finishConfirm(false);
      if (event.key === "Tab") {
        const buttons = dialogRef.current?.querySelectorAll("button:not(:disabled)");
        if (!buttons?.length) return;
        const first = buttons[0];
        const last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [dialog, finishConfirm]);

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    resolver.current?.(false);
  }, []);

  const value = useMemo(() => ({ notify, confirm }), [notify, confirm]);

  return (
    <FeedbackContext.Provider value={value}>
      {children}
      <div className={styles.toastStack} aria-live="polite" aria-relevant="additions text">
        {toasts.map((toast) => {
          const Icon = TOAST_ICONS[toast.type];
          return (
            <div key={toast.id} className={`${styles.toast} ${styles[toast.type]}`} role={toast.type === "error" ? "alert" : "status"}>
              <Icon className={styles.toastIcon} size={19} aria-hidden="true" />
              <div className={styles.toastContent}>
                <strong>{toast.title}</strong>
                <p>{toast.message}</p>
              </div>
              <button className={styles.closeButton} type="button" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification">
                <X size={17} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
      {dialog && (
        <div className={styles.backdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) finishConfirm(false); }}>
          <section ref={dialogRef} className={styles.dialog} role="alertdialog" aria-modal="true" aria-labelledby="feedback-dialog-title" aria-describedby="feedback-dialog-message">
            <div className={styles.dialogHeader}>
              <span className={`${styles.dialogIcon} ${dialog.variant === "danger" ? styles.dangerIcon : ""}`}>
                <AlertCircle size={21} aria-hidden="true" />
              </span>
              <h2 id="feedback-dialog-title">{dialog.title}</h2>
            </div>
            <p id="feedback-dialog-message" className={styles.dialogMessage}>{dialog.message}</p>
            <div className={styles.dialogActions}>
              <button ref={cancelButton} type="button" className={styles.cancelButton} onClick={() => finishConfirm(false)}>
                {dialog.cancelLabel}
              </button>
              <button
                type="button"
                className={`${styles.confirmButton} ${dialog.variant === "danger" ? styles.dangerButton : ""}`}
                onClick={() => finishConfirm(true)}
              >
                {dialog.confirmLabel}
              </button>
            </div>
          </section>
        </div>
      )}
    </FeedbackContext.Provider>
  );
}

export function useFeedback() {
  const value = useContext(FeedbackContext);
  if (!value) throw new Error("useFeedback must be used inside FeedbackProvider.");
  return value;
}
