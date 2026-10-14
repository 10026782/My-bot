import { useState } from "react";
import type { FccOverview } from "../types";
import { FAMILY_TABS, FAMILY_TAB_PREFIX, SCREEN_TITLE, familyCardModel, savingsTabModel, type FamilyTabKey } from "../lib/familyWealth";
import { panelId, tabId } from "../lib/fccTabs";
import { FccTabBar } from "./FccTabBar";
import { KpiCard } from "./FccKpiCard";
import { PortfolioLabPanel } from "./PortfolioLabPanel";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

/** Entry card on the FCC monthly tab. Wording only: every value is already in the overview. */
export function FamilyWealthCard({ data, onOpen }: { data: Pick<FccOverview, "summary" | "savings_release">; onOpen: () => void }) {
  const m = familyCardModel(data);
  return (
    <Surface variant="subtle" padding="compact" className="fcc-kpi fw-card" aria-label={m.title}>
      <p className="fcc-kpi__label">{m.title}</p>
      <p className="fcc-kpi__value">{m.value}</p>
      <p className="fcc-kpi__hint">{m.hint}</p>
      <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onOpen}>פתח</button>
    </Surface>
  );
}

function SavingsPanel({ data }: { data: Pick<FccOverview, "summary" | "savings_release"> }) {
  const m = savingsTabModel(data);
  return (
    <div className="fcc-stack">
      {!m.hasData && <ScreenState state="empty" title="עוד אין נתוני חיסכון" message="הגדירו יעד חיסכון חודשי במרכז הכלכלי." />}
      <div className="fcc-kpis">{m.rows.map((r) => <KpiCard key={r.key} label={r.label} value={r.value} hint={r.hint} />)}</div>
      {m.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </div>
  );
}

/** "תכנון חיסכון לטווח ארוך": two tabs. Read-only; nothing here writes (deposits are recorded in the FCC as before). */
export function FamilyWealth({ data, onBack }: { data: Pick<FccOverview, "summary" | "savings_release" | "as_of">; onBack: () => void }) {
  const [tab, setTab] = useState<FamilyTabKey>("savings");
  return (
    <main className="ventures-screen fcc-screen">
      <div className="ventures-shell">
        <PageHeader onBack={onBack} title={SCREEN_TITLE} eyebrow="BOSS · אישי" subtitle={`נכון ל-${data.as_of}`} />
        <div className="fcc-stack">
          <FccTabBar active={tab} onChange={setTab} tabs={FAMILY_TABS} idPrefix={FAMILY_TAB_PREFIX} ariaLabel="אזורי תכנון החיסכון" />
          <div role="tabpanel" id={panelId("savings", FAMILY_TAB_PREFIX)} aria-labelledby={tabId("savings", FAMILY_TAB_PREFIX)} hidden={tab !== "savings"}>
            <SavingsPanel data={data} />
          </div>
          {/* mounted only when opened: the simulation runs on demand, never in the background */}
          <div role="tabpanel" id={panelId("lab", FAMILY_TAB_PREFIX)} aria-labelledby={tabId("lab", FAMILY_TAB_PREFIX)} hidden={tab !== "lab"}>
            {tab === "lab" && <PortfolioLabPanel />}
          </div>
        </div>
      </div>
    </main>
  );
}
