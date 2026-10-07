import { FCC_TABS, panelId, tabId, type FccTabKey } from "../lib/fccTabs";

export function FccTabBar({ active, onChange }: { active: FccTabKey; onChange: (key: FccTabKey) => void }) {
  return (
    <div className="fcc-tabs" role="tablist" aria-label="אזורי המרכז הכלכלי">
      {FCC_TABS.map((t) => (
        <button key={t.key} type="button" role="tab" id={tabId(t.key)} aria-selected={active === t.key} aria-controls={panelId(t.key)}
                tabIndex={active === t.key ? 0 : -1} className={`fcc-tab ${active === t.key ? "fcc-tab--on" : ""}`}
                onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  );
}
