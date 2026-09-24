import "./globals.css";
import LayoutWrapper from "@/components/LayoutWrapper";

export const metadata = {
  title: "RichLead - Outreach Dashboard",
  description: "Automated Apollo + LLM Outreach",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <LayoutWrapper>
          {children}
        </LayoutWrapper>
      </body>
    </html>
  );
}
