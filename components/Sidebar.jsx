"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { authFetch } from "@/app/lib/api";
import { 
  LayoutDashboard, 
  Users, 
  CheckSquare, 
  Settings,
  Rocket,
  Mail,
  ShieldAlert,
  Inbox,
  ChevronLeft,
  ChevronRight,
  Search,
  ShieldCheck,
  Workflow,
  Activity,
  BadgeCheck,
} from "lucide-react";
import styles from "./Sidebar.module.css";

export default function Sidebar({ isMobileOpen = false, onNavigate }) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [canManageUsers, setCanManageUsers] = useState(false);
  const isSettingsActive = pathname.startsWith("/settings");

  useEffect(() => {
    let mounted = true;
    authFetch("/api/admin-dashboard/access/")
      .then((response) => {
        if (mounted) setCanManageUsers(response.ok);
      })
      .catch(() => {
        if (mounted) setCanManageUsers(false);
      });
    return () => { mounted = false; };
  }, []);

    const navItems = [
      { name: "Overview", path: "/dashboard", icon: LayoutDashboard },
      { name: "Prospecting", path: "/prospecting", icon: Search },
      { name: "Leads Database", path: "/leads", icon: Users },
      { name: "Smart Inbox", path: "/inbox", icon: Inbox },
      { name: "Review Queue", path: "/review", icon: CheckSquare },
      { name: "Email Sequences", path: "/campaigns", icon: Workflow },
      { name: "Deliverability", path: "/deliverability", icon: Activity },
      { name: "Lead Quality", path: "/lead-quality", icon: BadgeCheck },
      { name: "Sender Accounts", path: "/senders", icon: Mail },
      { name: "Global Suppression", path: "/suppression", icon: ShieldAlert },
      ...(canManageUsers ? [{ name: "Admin Dashboard", path: "/admin-dashboard", icon: ShieldCheck }] : []),
    ];

  return (
    <aside id="app-sidebar" className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ""} ${isMobileOpen ? styles.mobileOpen : ""}`}>
      <div className={styles.logo}>
        <Rocket className={styles.logoIcon} />
        <span>RichLead</span>
      </div>
      
      <div className={styles.pinnedNav} role="group" aria-label="Pinned navigation">
        <Link
          href="/settings"
          className={`${styles.navItem} ${isSettingsActive ? styles.active : ""}`}
          title={isCollapsed ? "Settings" : undefined}
          onClick={onNavigate}
        >
          <Settings size={20} />
          <span>Settings</span>
        </Link>

        <button
          type="button"
          className={`${styles.navItem} ${styles.toggleBtn}`}
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{ width: "100%" }}
        >
          {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          <span>{isCollapsed ? "" : "Collapse"}</span>
        </button>
      </div>

      <nav className={styles.nav} aria-label="Main navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path || pathname.startsWith(`${item.path}/`);
          
          return (
            <Link 
              key={item.path} 
              href={item.path} 
              className={`${styles.navItem} ${isActive ? styles.active : ""}`}
              title={isCollapsed ? item.name : undefined}
              onClick={onNavigate}
            >
              <Icon size={20} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

    </aside>
  );
}
