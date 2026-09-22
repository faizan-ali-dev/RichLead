import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import styles from "@/components/Layout.module.css";

export const metadata = {
  title: "RichLead - Outreach Dashboard",
  description: "Automated Apollo + LLM Outreach",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className={styles.layout}>
          <Sidebar />
          <div className={styles.mainContent}>
            <TopNav />
            <main className={styles.pageContent}>
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
