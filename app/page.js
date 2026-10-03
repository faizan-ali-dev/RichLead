import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  Compass,
  Inbox,
  Layers3,
  LockKeyhole,
  Mail,
  Rocket,
  Search,
  Sparkles,
  Target,
  Workflow,
} from "lucide-react";
import styles from "./page.module.css";

export const metadata = {
  title: "RichLead | Turn thoughtful outreach into a stronger pipeline",
  description: "Find and qualify leads, prepare relevant outreach, and manage replies in one focused workspace.",
};

const capabilities = [
  {
    icon: Search,
    title: "Find the right leads",
    description: "Discover companies and contacts through the providers you connect, then keep useful details in one place.",
  },
  {
    icon: Target,
    title: "Qualify with context",
    description: "Use business details and your ideal customer profile to focus on prospects that fit your goals.",
  },
  {
    icon: Sparkles,
    title: "Write with relevance",
    description: "Create personalized drafts from your company information, lead context, and preferred outreach language.",
  },
  {
    icon: CheckCircle2,
    title: "Review before sending",
    description: "Keep control with a clear review queue and approve messages one by one or in bulk.",
  },
  {
    icon: Inbox,
    title: "Keep every reply close",
    description: "Follow conversations from connected mailboxes and jump from reply notifications to the right thread.",
  },
  {
    icon: BarChart3,
    title: "See real activity",
    description: "Understand lead discovery, messages, and replies through analytics based on your workspace data.",
  },
];

const steps = [
  {
    number: "01",
    title: "Connect your sources",
    description: "Choose lead providers, mailboxes, and AI services that fit your workflow.",
  },
  {
    number: "02",
    title: "Build a focused list",
    description: "Search, qualify, and organize relevant companies and contacts.",
  },
  {
    number: "03",
    title: "Reach out with care",
    description: "Review tailored messages, send them from your mailbox, and keep up with replies.",
  },
];

function BrandMark({ compact = false }) {
  return (
    <span className={compact ? styles.brandMarkCompact : styles.brandMark} aria-hidden="true">
      <Rocket size={compact ? 17 : 20} strokeWidth={2.3} />
    </span>
  );
}

function WorkspacePreview() {
  return (
    <div className={styles.previewWrap} aria-label="Illustrative RichLead workspace preview">
      <div className={styles.previewGlow} aria-hidden="true" />
      <div className={styles.previewCard}>
        <div className={styles.previewTop}>
          <div className={styles.previewBrand}>
            <BrandMark compact />
            <span>RichLead</span>
          </div>
          <span className={styles.previewBadge}>Workspace preview</span>
        </div>
        <div className={styles.previewHeading}>
          <div>
            <p className={styles.previewKicker}>CAMPAIGN WORKSPACE</p>
            <h2>Your pipeline, in focus</h2>
          </div>
          <span className={styles.previewDots} aria-hidden="true"><i /><i /><i /></span>
        </div>
        <div className={styles.previewMetrics}>
          <div className={styles.previewMetric}>
            <span>Discover</span>
            <div className={styles.metricVisual}><span /><span /><span /><span /><span /></div>
          </div>
          <div className={styles.previewMetric}>
            <span>Review</span>
            <div className={styles.reviewVisual}><Check size={15} /><i /><i /></div>
          </div>
          <div className={styles.previewMetric}>
            <span>Replies</span>
            <div className={styles.replyVisual}><span /><span /><span /></div>
          </div>
        </div>
        <div className={styles.previewSectionHead}>
          <span>Recent prospects</span>
          <span>View pipeline <ArrowRight size={13} /></span>
        </div>
        <div className={styles.prospectRow}>
          <span className={styles.prospectIcon}><Layers3 size={15} /></span>
          <span className={styles.prospectName}><strong>Northstar Labs</strong><small>Software · United States</small></span>
          <span className={styles.prospectStatus}><i /> Qualified</span>
        </div>
        <div className={styles.prospectRow}>
          <span className={styles.prospectIcon + " " + styles.prospectIconAlt}><Compass size={15} /></span>
          <span className={styles.prospectName}><strong>Meridian Systems</strong><small>Technology · United Kingdom</small></span>
          <span className={styles.prospectStatus}><i /> In review</span>
        </div>
        <div className={styles.previewBottom}>
          <span><Mail size={14} /> Connected mailbox</span>
          <span><LockKeyhole size={13} /> You stay in control</span>
        </div>
      </div>
      <div className={styles.floatingNote}>
        <span className={styles.floatingIcon}><Workflow size={17} /></span>
        <span><strong>One clear workflow</strong><small>Discover, review, follow up</small></span>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className={styles.landing}>
      <header className={styles.header}>
        <div className={styles.navInner}>
          <Link className={styles.brand} href="/" aria-label="RichLead home">
            <BrandMark />
            <span>RichLead</span>
          </Link>
          <nav className={styles.navLinks} aria-label="Main navigation">
            <Link href="#features">Features</Link>
            <Link href="#workflow">How it works</Link>
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/terms">Terms and Conditions</Link>
          </nav>
          <div className={styles.navActions}>
            <Link className={styles.loginButton} href="/login">Log in</Link>
            <Link className={styles.navCta} href="/register">Get started <ArrowRight size={16} /></Link>
          </div>
        </div>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroGrid} aria-hidden="true" />
        <div className={styles.heroInner}>
          <div className={styles.heroCopy}>
            <p className={styles.announcement}><span /> A more thoughtful way to build your pipeline</p>
            <h1>Find the right leads. <span>Make every follow-up count.</span></h1>
            <p className={styles.heroDescription}>
              Bring lead discovery, research, outreach, and replies into one focused workspace.
              Build stronger conversations without losing sight of the details.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryCta} href="/register">Get started <ArrowRight size={18} /></Link>
              <Link className={styles.secondaryCta} href="/login">Log in to your account</Link>
            </div>
            <div className={styles.heroAssurance}>
              <span><Check size={15} /> Review before sending</span>
              <span><Check size={15} /> Your connected accounts</span>
            </div>
          </div>
          <WorkspacePreview />
        </div>
        <a className={styles.scrollCue} href="#features"><span>Explore RichLead</span><ArrowDown size={15} /></a>
      </section>

      <section className={styles.providerStrip} aria-label="Connect your workflow">
        <p>Bring your outreach workflow together</p>
        <div><span>Apollo</span><span>Hunter</span><span><Mail size={16} /> Mailboxes</span><span><Sparkles size={16} /> AI providers</span></div>
      </section>

      <section className={styles.featuresSection} id="features">
        <div className={styles.sectionIntro}>
          <p className={styles.sectionEyebrow}>A workspace that keeps the details connected</p>
          <h2>From first search to thoughtful follow-up</h2>
          <p>Keep prospecting, message review, and conversation history in one calm, organized place.</p>
        </div>
        <div className={styles.featureGrid}>
          {capabilities.map(({ icon: Icon, title, description }, index) => (
            <article className={styles.featureCard} key={title} style={{ "--card-index": index }}>
              <span className={styles.featureIcon}><Icon size={21} strokeWidth={1.8} /></span>
              <h3>{title}</h3>
              <p>{description}</p>
              <span className={styles.cardArrow} aria-hidden="true"><ArrowRight size={16} /></span>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.workflowSection} id="workflow">
        <div className={styles.workflowIntro}>
          <p className={styles.sectionEyebrow}>A simple, controlled process</p>
          <h2>Move from prospect to conversation with confidence.</h2>
          <p>RichLead gives your team a consistent place to prepare outreach and stay on top of every reply.</p>
          <Link className={styles.textCta} href="/register">Start building your pipeline <ArrowRight size={17} /></Link>
        </div>
        <div className={styles.steps}>
          {steps.map((step) => (
            <article className={styles.step} key={step.number}>
              <div className={styles.stepTop}><span>{step.number}</span><i /></div>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.finalCta}>
        <div className={styles.ctaOrb} aria-hidden="true" />
        <span className={styles.finalIcon}><Rocket size={21} /></span>
        <p className={styles.sectionEyebrow}>Make your next campaign more intentional</p>
        <h2>Build a pipeline you can actually follow.</h2>
        <p>Bring your leads, outreach, and replies together with RichLead.</p>
        <Link className={styles.primaryCta} href="/register">Get started <ArrowRight size={18} /></Link>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <Link className={styles.brand} href="/" aria-label="RichLead home">
            <BrandMark compact /><span>RichLead</span>
          </Link>
          <p>Lead discovery and outreach, brought into focus.</p>
          <nav aria-label="Legal and account links">
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/terms">Terms and Conditions</Link>
            <Link href="/login">Log in</Link>
          </nav>
          <span className={styles.copyright}>© {new Date().getFullYear()} RichLead</span>
        </div>
      </footer>
    </main>
  );
}
