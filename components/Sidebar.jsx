"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Users, 
  CheckSquare, 
  Settings2, 
  Settings,
  Rocket,
  Mail,
  ListTree
} from "lucide-react";
import styles from "./Sidebar.module.css";

export default function Sidebar() {
  const pathname = usePathname();

  const navItems = [
    { name: "Overview", path: "/", icon: LayoutDashboard },
    { name: "Leads Database", path: "/leads", icon: Users },
    { name: "Review Queue", path: "/review", icon: CheckSquare },
    { name: "Campaigns", path: "/campaigns", icon: Settings2 },
    { name: "Multi-step Sequences", path: "/sequences", icon: ListTree },
    { name: "Sender Accounts", path: "/senders", icon: Mail },
  ];

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <Rocket className={styles.logoIcon} />
        <span>RichLead</span>
      </div>
      
      <nav className={styles.nav}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path;
          
          return (
            <Link 
              key={item.path} 
              href={item.path} 
              className={`${styles.navItem} ${isActive ? styles.active : ""}`}
            >
              <Icon size={20} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className={styles.bottomNav}>
        <Link 
          href="/settings" 
          className={`${styles.navItem} ${pathname === "/settings" ? styles.active : ""}`}
          style={{ padding: "0.75rem 0" }}
        >
          <Settings size={20} />
          Settings
        </Link>
      </div>
    </aside>
  );
}
