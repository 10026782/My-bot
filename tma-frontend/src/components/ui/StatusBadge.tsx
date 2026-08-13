import type { ReactNode } from "react";

interface StatusBadgeProps {
  children: ReactNode;
  tone?: "neutral" | "info" | "warning" | "success" | "danger";
}

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  return <span className={`boss-status-badge boss-status-badge--${tone}`}>{children}</span>;
}
