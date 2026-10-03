import Link from "next/link";
import { ArrowLeft, Rocket } from "lucide-react";
import styles from "./LegalPage.module.css";

const documents = {
  terms: {
    title: "Terms of Service",
    intro: "These terms explain the basic rules for using RichLead. By creating an account or using the service, you agree to follow them.",
    sections: [
      {
        title: "Using RichLead",
        paragraphs: [
          "RichLead provides tools for managing leads, preparing outreach, connecting mailboxes, and reviewing campaign activity. Features can change as the service develops.",
          "Keep your account details secure and make sure the information you add is accurate. You are responsible for activity performed through your account and for keeping your connected accounts and API credentials under your control.",
        ],
      },
      {
        title: "Your data and outreach",
        paragraphs: [
          "You keep responsibility for the lead and message content you add or create. You must have the rights and permissions needed to use contact data and send messages to those recipients.",
          "Follow the laws and provider rules that apply to your outreach, including consent, identification, unsubscribe, and privacy requirements. Do not use RichLead to send unlawful, deceptive, threatening, or unwanted bulk messages.",
          "AI-generated drafts can be incomplete or inaccurate. Review every draft and recipient before sending. If you enable automated sending, you are responsible for the settings and messages sent through that feature.",
        ],
      },
      {
        title: "Connected services",
        paragraphs: [
          "When you connect a mailbox or an AI provider, you authorize RichLead to use that connection to provide the features you request. Those providers may apply their own terms, privacy notices, usage limits, and security practices.",
          "You can disconnect a provider from RichLead. Disconnecting may stop related features, but it does not necessarily delete data already stored by RichLead or by that provider.",
        ],
      },
      {
        title: "Availability and changes",
        paragraphs: [
          "We work to keep RichLead available, but we do not promise uninterrupted access, a particular delivery rate, or specific business results. We may change or suspend a feature to maintain or protect the service.",
          "We may update these terms as the product changes. The latest version will be published on this page; continued use after an update means you accept the revised terms.",
        ],
      },
      {
        title: "Contact",
        paragraphs: [
          <>Questions about these terms? Email <a href="mailto:faizancode68@gmail.com">faizancode68@gmail.com</a>.</>,
        ],
      },
    ],
  },
  privacy: {
    title: "Privacy Policy",
    intro: "This page describes the information RichLead handles to provide its lead-management and outreach features.",
    sections: [
      {
        title: "Information you provide",
        paragraphs: [
          "This can include your name, email address, login details, business settings, lead names and contact details, notes, prompts, generated drafts, suppression choices, and campaign settings.",
          "If you connect a mailbox, RichLead may store messages and message details needed to show your inbox and link replies to leads. If you connect an AI provider or mailbox, RichLead stores the credentials or authorization tokens needed to use that connection.",
        ],
      },
      {
        title: "How information is used",
        paragraphs: [
          "We use this information to operate your account, manage leads, create drafts when requested, send or sync email through the mailbox you connect, display dashboard activity, protect the service, and respond to support requests.",
          "When you request AI generation, relevant lead details and your instructions are sent to the AI provider configured for your account. Email is sent or synchronized through the mailbox provider you connect. Those providers handle data under their own privacy terms.",
          "RichLead also collects limited first-party usage analytics, including page paths, named landing-page link clicks, an anonymous session identifier, and event times. We use these events to understand traffic and improve the service. Analytics records do not include message contents, passwords, or IP addresses, and only RichLead administrators can view them.",
        ],
      },
      {
        title: "Storage, sharing, and security",
        paragraphs: [
          "Account data is used to provide RichLead to you. We do not sell your personal information. Information may be processed by hosting and service providers that help operate RichLead, or disclosed when required to protect users, the service, or comply with law.",
          "Connected API credentials, mailbox passwords, and OAuth tokens are encrypted by the application before storage. We also use account authentication and access controls, but no online service can guarantee perfect security.",
        ],
      },
      {
        title: "Retention and your choices",
        paragraphs: [
          "RichLead keeps account content while it is needed to operate your account and features. Disconnecting an integration stops future use of that connection, but does not by itself remove previously synced messages or other saved content.",
          <>To request access, correction, or deletion of account data, email <a href="mailto:faizancode68@gmail.com">faizancode68@gmail.com</a> from the email address associated with your account. Some copies may remain in protected backups until those backups expire, or be retained where the law requires it.</>,
        ],
      },
      {
        title: "Updates and contact",
        paragraphs: [
          "We may update this policy when RichLead's features or data practices change. The current version will be available on this page.",
          <>For privacy questions or requests, email <a href="mailto:faizancode68@gmail.com">faizancode68@gmail.com</a>.</>,
        ],
      },
    ],
  },
};

export default function LegalPage({ type }) {
  const document = documents[type];
  if (!document) return null;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.brand} href="/" aria-label="RichLead home">
          <span className={styles.brandMark}><Rocket size={19} /></span>
          <span>RichLead</span>
        </Link>
        <nav className={styles.nav} aria-label="Account links">
          <Link href="/terms" aria-current={type === "terms" ? "page" : undefined}>Terms</Link>
          <Link href="/privacy" aria-current={type === "privacy" ? "page" : undefined}>Privacy</Link>
          <Link className={styles.signIn} href="/login">Sign in</Link>
        </nav>
      </header>

      <article className={styles.document}>
        <Link className={styles.backLink} href="/register"><ArrowLeft size={16} /> Back to sign up</Link>
        <p className={styles.eyebrow}>RichLead · Updated September 29, 2026</p>
        <h1>{document.title}</h1>
        <p className={styles.intro}>{document.intro}</p>
        <div className={styles.sections}>
          {document.sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              {section.paragraphs.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </section>
          ))}
        </div>
      </article>

      <footer className={styles.footer}>
        <span>© {new Date().getFullYear()} RichLead</span>
        <span>Lead outreach workspace</span>
      </footer>
    </main>
  );
}
