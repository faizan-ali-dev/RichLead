import "./globals.css";
import LayoutWrapper from "@/components/LayoutWrapper";
import { FeedbackProvider } from "@/components/FeedbackProvider";

export const metadata = {
  title: "RichLead - Outreach Dashboard",
  description: "Automated Apollo + LLM Outreach",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <LayoutWrapper>
          <FeedbackProvider>{children}</FeedbackProvider>
        </LayoutWrapper>
      </body>
    </html>
  );
}
