import SettingsModule from "@/components/SettingsModule";
import FollowUpCard from "../FollowUpCard";
import SendTimeCard from "../SendTimeCard";

export default function FollowUpSettingsPage() {
  return (
    <SettingsModule
      title="Follow-ups & compliance"
      description="Set the follow-up schedule, send-time optimization, and unsubscribe behavior used in outreach."
    >
      <FollowUpCard />
      <SendTimeCard />
    </SettingsModule>
  );
}
