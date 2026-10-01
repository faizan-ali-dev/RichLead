import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  Briefcase,
  Cpu,
  KeyRound,
  Languages,
  Repeat,
  UserRound,
  Webhook,
  Zap,
} from "lucide-react";
import styles from "./page.module.css";

const settingsModules = [
  { href: "/settings/autopilot", title: "Autopilot", detail: "Control automatic outreach and review behavior.", icon: Zap },
  { href: "/settings/business", title: "Business profile", detail: "Manage the facts and proof points used in drafts.", icon: Briefcase },
  { href: "/settings/outreach", title: "Reachout language", detail: "Choose the language RichLead uses for AI-written outreach drafts.", icon: Languages },
  { href: "/settings/ai", title: "AI provider", detail: "Connect a provider, choose a model, and test it.", icon: Cpu },
  { href: "/settings/prompts", title: "Prompts", detail: "Set writing instructions and review safety rules.", icon: Bot },
  { href: "/settings/follow-ups", title: "Follow-ups & compliance", detail: "Configure follow-up timing and unsubscribe behavior.", icon: Repeat },
  { href: "/settings/integrations", title: "API integrations", detail: "Manage connected data provider keys.", icon: KeyRound },
  { href: "/settings/webhooks", title: "CRM webhooks", detail: "View CRM event delivery support and status.", icon: Webhook },
  { href: "/settings/profile", title: "Account profile", detail: "View the account identity used by RichLead.", icon: UserRound },
];

export default function SettingsPage() {
  return (
    <div className={`${styles.page} animate-fade-in`}>
      <header>
        <h2 className={styles.sectionTitle}>Settings</h2>
        <p className={styles.settingsIntro}>Each area has its own page, so settings stay organized as RichLead grows.</p>
      </header>
      <div className={styles.settingsGrid}>
        {settingsModules.map(({ href, title, detail, icon: Icon }) => (
          <Link key={href} href={href} className={styles.settingsCard}>
            <span className={styles.settingsCardIcon}><Icon size={20} /></span>
            <span className={styles.settingsCardCopy}>
              <strong>{title}</strong>
              <span>{detail}</span>
            </span>
            <ArrowUpRight size={17} className={styles.settingsCardArrow} />
          </Link>
        ))}
      </div>
    </div>
  );
}
