import { Rocket } from "lucide-react";
import Link from "next/link";
import styles from "./AuthShell.module.css";

export default function AuthShell({ children, quote = "The right conversations can change everything." }) {
  return (
    <main className={styles.page}>
      <div className={styles.glowOne} aria-hidden="true" />
      <div className={styles.glowTwo} aria-hidden="true" />
      <div className={styles.shell}>
        <section className={styles.formPanel}>{children}</section>
        <aside className={styles.brandPanel}>
          <div>
            <div className={styles.brandLockup}>
              <span className={styles.logo} aria-hidden="true"><Rocket size={26} /></span>
              <span className={styles.brandName}>Rich Lead</span>
            </div>
            <p className={styles.eyebrow}>OUTREACH, WITH INTENTION</p>
          </div>
          <div className={styles.quoteBlock}>
            <span className={styles.quoteMark} aria-hidden="true">“</span>
            <blockquote>{quote}</blockquote>
            <p>Build genuine connections, one thoughtful conversation at a time.</p>
          </div>
          <div className={styles.brandFooter}>
            <span>Find the people who move your business forward.</span>
            <nav className={styles.legalLinks} aria-label="Legal information">
              <Link href="/terms">Terms</Link>
              <Link href="/privacy">Privacy</Link>
            </nav>
          </div>
        </aside>
      </div>
    </main>
  );
}
