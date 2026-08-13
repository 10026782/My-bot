import type { ReactNode } from "react";

interface PageHeaderProps {
  title: ReactNode;
  eyebrow?: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  action?: ReactNode;
  onBack?: () => void;
  backLabel?: string;
}

export function PageHeader({
  title,
  eyebrow,
  subtitle,
  badge,
  action,
  onBack,
  backLabel = "חזרה",
}: PageHeaderProps) {
  return (
    <header className="boss-page-header">
      <div className="boss-page-header__topline">
        {onBack && (
          <button type="button" onClick={onBack} className="boss-button boss-button--quiet boss-bubble--action">
            {backLabel}
          </button>
        )}
        <div className="boss-page-header__spacer" />
        {action}
      </div>

      <div className="boss-page-header__body">
        <div className="boss-page-header__copy">
          {eyebrow && <p className="boss-eyebrow">{eyebrow}</p>}
          <div className="boss-page-header__title-row">
            <h1 className="boss-page-title">{title}</h1>
            {badge}
          </div>
          {subtitle && <p className="boss-page-subtitle">{subtitle}</p>}
        </div>
      </div>
    </header>
  );
}
