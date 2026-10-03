"use client";

import { useEffect, useState } from "react";
import {
  AtSign,
  BriefcaseBusiness,
  Camera,
  CirclePlay,
  Code2,
  Link2,
  MessageCircle,
  Music2,
  Send,
  Users,
} from "lucide-react";
import { API_BASE } from "@/app/lib/api";
import styles from "./SocialLinks.module.css";

const SOCIAL_ICONS = {
  linkedin: BriefcaseBusiness,
  x: AtSign,
  facebook: Users,
  instagram: Camera,
  youtube: CirclePlay,
  tiktok: Music2,
  threads: AtSign,
  github: Code2,
  reddit: MessageCircle,
  discord: MessageCircle,
  whatsapp: Send,
  other: Link2,
};

export default function SocialLinks() {
  const [links, setLinks] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/admin-dashboard/social-links/`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : []))
      .then((data) => {
        if (Array.isArray(data)) setLinks(data);
      })
      .catch((error) => {
        if (error.name !== "AbortError") setLinks([]);
      });
    return () => controller.abort();
  }, []);

  if (!links.length) return null;

  return (
    <nav className={styles.socialLinks} aria-label="RichLead social accounts">
      {links.map((link) => {
        const Icon = SOCIAL_ICONS[link.platform] || Link2;
        return (
          <a
            className={styles.socialLink}
            key={link.id}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={link.label}
            title={link.label}
            data-analytics-label={`social_${link.platform}_${link.id}`}
          >
            <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
          </a>
        );
      })}
    </nav>
  );
}
