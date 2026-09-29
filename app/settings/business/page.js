import SettingsModule from "@/components/SettingsModule";
import BusinessInfoCard from "../BusinessInfoCard";

export default function BusinessSettingsPage() {
  return (
    <SettingsModule
      title="Business profile"
      description="Keep the information used by RichLead’s AI drafts accurate and specific."
    >
      <BusinessInfoCard />
    </SettingsModule>
  );
}
