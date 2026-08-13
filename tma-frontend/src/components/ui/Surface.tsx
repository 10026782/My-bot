import type { HTMLAttributes, ReactNode } from "react";

interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: "default" | "subtle" | "raised";
  padding?: "none" | "compact" | "comfortable";
}

export function Surface({
  children,
  variant = "default",
  padding = "comfortable",
  className = "",
  ...props
}: SurfaceProps) {
  return (
    <div
      className={`boss-surface boss-surface--${variant} boss-surface--${padding} ${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  );
}
