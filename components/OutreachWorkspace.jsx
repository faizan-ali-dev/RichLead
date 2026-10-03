import Link from "next/link";
import { ArrowUpRight, CircleHelp, LoaderCircle } from "lucide-react";
import styles from "./OutreachWorkspace.module.css";

export function WorkspaceHeader({ eyebrow, title, description, action }) {
  return (
    <header className={styles.header}>
      <div>
        {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
        <h2 className={styles.pageTitle}>{title}</h2>
        <p className={styles.description}>{description}</p>
      </div>
      {action && <div className={styles.headerAction}>{action}</div>}
    </header>
  );
}

export function WorkspaceStats({ items }) {
  return (
    <div className={styles.statsGrid}>
      {items.map(({ label, value, detail, icon: Icon }) => (
        <article className={styles.statCard} key={label}>
          <div className={styles.statTop}>
            <span>{label}</span>
            {Icon && <Icon size={17} aria-hidden="true" />}
          </div>
          <strong>{value ?? "—"}</strong>
          {detail && <small>{detail}</small>}
        </article>
      ))}
    </div>
  );
}

export function WorkspaceNotice({ children, tone = "info" }) {
  return (
    <div className={`${styles.notice} ${styles[tone]}`}>
      <CircleHelp size={17} aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

export function WorkspacePanel({ title, description, action, children, className = "" }) {
  return (
    <section className={`${styles.panel} ${className}`}>
      {(title || description || action) && (
        <div className={styles.panelHeader}>
          <div>
            {title && <h3>{title}</h3>}
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatusBadge({ status, children }) {
  const className = status === "active" || status === "available" || status === "verified" || status === "completed" || status === "connected"
    ? styles.statusGood
    : status === "paused" || status === "near_limit" || status === "unknown" || status === "pending"
      ? styles.statusWarning
      : status === "failed" || status === "stopped" || status === "disconnected" || status === "not_verified" || status === "limit_reached"
        ? styles.statusBad
        : styles.statusNeutral;
  return <span className={`${styles.statusBadge} ${className}`}>{children || String(status || "Unknown").replaceAll("_", " ")}</span>;
}

export function WorkspaceLoading({ label = "Loading workspace data" }) {
  return <div className={styles.loading}><LoaderCircle size={18} className={styles.spinner} />{label}</div>;
}

export function WorkspaceEmpty({ title, description, href, actionLabel }) {
  return (
    <div className={styles.emptyState}>
      <h4>{title}</h4>
      <p>{description}</p>
      {href && actionLabel && <Link href={href} className={styles.textLink}>{actionLabel}<ArrowUpRight size={15} /></Link>}
    </div>
  );
}

export function formatWorkspaceDate(value) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
