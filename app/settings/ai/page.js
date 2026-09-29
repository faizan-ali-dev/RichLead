import SettingsModule from "@/components/SettingsModule";
import LlmProviderCard from "../LlmProviderCard";

export default function AiSettingsPage() {
  return (
    <SettingsModule
      title="AI provider"
      description="Connect an AI provider, select a model, and test the connection."
    >
      <LlmProviderCard />
    </SettingsModule>
  );
}
