import "./globals.css";
import LayoutWrapper from "@/components/LayoutWrapper";
import { FeedbackProvider } from "@/components/FeedbackProvider";
import AnalyticsTracker from "@/components/AnalyticsTracker";

export const metadata = {
  title: "RichLead | Lead discovery and outreach",
  description: "Find and qualify leads, prepare thoughtful outreach, and manage replies in one focused workspace.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <LayoutWrapper>
          <FeedbackProvider>
            <AnalyticsTracker />
            {children}
          </FeedbackProvider>
        </LayoutWrapper>
      </body>
    </html>
  );
}
