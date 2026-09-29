import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import styles from "./SettingsModule.module.css";

export default function SettingsModule({ title, description, children }) {
  return (
    <div className={`${styles.page} animate-fade-in`}>
      <Link href="/settings" className={styles.backLink}>
        <ArrowLeft size={16} /> All settings
      </Link>
      <header className={styles.header}>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </header>
      {children}
    </div>
  );
}
