"use client";

import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import TopNav from "./TopNav";
import styles from "./Layout.module.css";

export default function LayoutWrapper({ children }) {
  const pathname = usePathname();
  const isAuthPage = pathname === "/login" || pathname === "/register";

  if (isAuthPage) {
    return (
      <div className={styles.layout}>
        <div className={styles.mainContent} style={{ marginLeft: 0, width: '100vw' }}>
          <main className={styles.pageContent} style={{ padding: 0 }}>
            {children}
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.layout}>
      <Sidebar />
      <div className={styles.mainContent}>
        <TopNav />
        <main className={styles.pageContent}>
          {children}
        </main>
      </div>
    </div>
  );
}
