import SettingsModule from "@/components/SettingsModule";
import FollowUpCard from "../FollowUpCard";

export default function FollowUpSettingsPage() {
  return (
    <SettingsModule
      title="Follow-ups & compliance"
      description="Set the follow-up schedule and the unsubscribe behavior used in outreach."
    >
      <FollowUpCard />
    </SettingsModule>
  );
}
