import type { KeyboardEvent } from "react";
import { FCC_TABS, panelId, tabForKey, tabId, type FccTabKey } from "../lib/fccTabs";

export function FccTabBar({ active, onChange }: { active: FccTabKey; onChange: (key: FccTabKey) => void }) {
  // roving tabindex: only the selected tab is in the Tab order, so the arrows must reach the others
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const next = tabForKey(active, e.key, rtl);
    if (!next) return;
    e.preventDefault();
    onChange(next);
    document.getElementById(tabId(next))?.focus();
  };
  return (
    <div className="fcc-tabs" role="tablist" aria-label="אזורי המרכז הכלכלי" onKeyDown={onKeyDown}>
      {FCC_TABS.map((t) => (
        <button key={t.key} type="button" role="tab" id={tabId(t.key)} aria-selected={active === t.key} aria-controls={panelId(t.key)}
                tabIndex={active === t.key ? 0 : -1} className={`fcc-tab ${active === t.key ? "fcc-tab--on" : ""}`}
                onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  );
}
