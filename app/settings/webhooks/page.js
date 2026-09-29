import { Webhook } from "lucide-react";
import SettingsModule from "@/components/SettingsModule";
import styles from "../page.module.css";

export default function WebhookSettingsPage() {
  return (
    <SettingsModule title="CRM webhooks" description="Manage event delivery to tools such as Zapier or HubSpot.">
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}><Webhook size={20} className="text-accent-primary" /> Webhook delivery</h3>
        <div className={styles.warnBanner}>
          Webhook URL controls were previously shown here, but RichLead does not currently have an API to save or deliver these events. They are not configured or active.
        </div>
        <p className={styles.hint}>This route is separated so webhook delivery can be added here later without changing other settings pages.</p>
      </section>
    </SettingsModule>
  );
}
