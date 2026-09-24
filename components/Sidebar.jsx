"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { 
  LayoutDashboard, 
  Users, 
  CheckSquare, 
  Settings2, 
  Settings,
  Rocket,
  Mail,
  ListTree,
  ShieldAlert,
  Inbox,
  ChevronLeft,
  ChevronRight,
  Search
} from "lucide-react";
import styles from "./Sidebar.module.css";

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);

    const navItems = [
      { name: "Overview", path: "/", icon: LayoutDashboard },
      { name: "Prospecting", path: "/prospecting", icon: Search },
      { name: "Leads Database", path: "/leads", icon: Users },
      { name: "Smart Inbox", path: "/inbox", icon: Inbox },
      { name: "Review Queue", path: "/review", icon: CheckSquare },
      { name: "Multi-step Sequences", path: "/sequences", icon: ListTree },
      { name: "Sender Accounts", path: "/senders", icon: Mail },
      { name: "Global Suppression", path: "/suppression", icon: ShieldAlert },
    ];

  return (
    <aside className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ""}`}>
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
              title={isCollapsed ? item.name : undefined}
            >
              <Icon size={20} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className={styles.bottomNav}>
        <Link 
          href="/settings" 
          className={`${styles.navItem} ${pathname === "/settings" ? styles.active : ""}`}
          style={{ padding: isCollapsed ? "0.75rem 0" : "0.75rem 1.5rem" }}
          title={isCollapsed ? "Settings" : undefined}
        >
          <Settings size={20} />
          <span>Settings</span>
        </Link>

        <button 
          className={`${styles.navItem} ${styles.toggleBtn}`} 
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          style={{ padding: isCollapsed ? "0.75rem 0" : "0.75rem 1.5rem", width: '100%' }}
        >
          {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          <span>{isCollapsed ? "" : "Collapse"}</span>
        </button>
      </div>
    </aside>
  );
}
