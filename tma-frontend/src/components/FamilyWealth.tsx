import { useEffect, useState } from "react";
import { fetchFccOverview } from "../api";
import type { FccOverview } from "../types";
import { FAMILY_TABS, FAMILY_TAB_PREFIX, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, familyCardModel, savingsTabModel, type FamilyTabKey } from "../lib/familyWealth";
import { panelId, tabId } from "../lib/fccTabs";
import { FccTabBar } from "./FccTabBar";
import { KpiCard } from "./FccKpiCard";
import { PortfolioLabPanel } from "./PortfolioLabPanel";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

/** Entry card on the FCC monthly tab. Wording only: every value is already in the overview. */
export function FamilyWealthCard({ data, onOpen }: { data: Pick<FccOverview, "summary" | "savings_release" | "savings_history">; onOpen: () => void }) {
  const m = familyCardModel(data);
  return (
    <Surface variant="subtle" padding="compact" className="fcc-kpi fw-card" aria-label={m.title}>
      <p className="fcc-kpi__label">{m.title}</p>
      <p className="fcc-kpi__value">{m.value}</p>
      <p className="fcc-kpi__hint">{m.hint}</p>
      <button type="button" className="boss-button boss-button--quiet boss-bubble--action" aria-label={OPEN_LABEL} onClick={onOpen}>פתח</button>
    </Surface>
  );
}

function SavingsPanel({ data }: { data: Pick<FccOverview, "summary" | "savings_release" | "savings_history"> }) {
  const m = savingsTabModel(data);
  return (
    <div className="fcc-stack">
      {!m.hasData && <ScreenState state="empty" title="עוד אין נתוני חיסכון" message="הגדירו יעד חיסכון חודשי במרכז הכלכלי." />}
      <div className="fcc-kpis">{m.rows.map((r) => <KpiCard key={r.key} label={r.label} value={r.value} hint={r.hint} />)}</div>
      {m.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </div>
  );
}

type SavingsData = Pick<FccOverview, "summary" | "savings_release" | "savings_history" | "as_of">;
export type OverviewState = { status: "loading" } | { status: "ok"; data: SavingsData } | { status: "error"; code?: number };

/** The savings tab's three states. The lab tab does not depend on this: it has its own call and its own states. */
function SavingsSection({ overview, onRetry }: { overview: OverviewState; onRetry: () => void }) {
  if (overview.status === "loading") return <ScreenState state="loading" title="טוען את נתוני החיסכון" message="אוסף את התמונה העדכנית…" />;
  if (overview.status === "error") {
    const closed = overview.code === 404, forbidden = overview.code === 401 || overview.code === 403;
    return (
      <ScreenState state="error" title={closed ? "המסך עדיין לא פעיל" : forbidden ? "אין הרשאה" : "לא הצלחנו לטעון"}
                   message={closed ? "נתוני החיסכון אינם זמינים בחשבון הזה." : forbidden ? "המסך אישי ונגיש לבעל הרשומה בלבד." : "אפשר לנסות שוב בעוד רגע."}
                   action={!closed && !forbidden && (
                     <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={onRetry}>נסו שוב</button>
                   )} />
    );
  }
  return <SavingsPanel data={overview.data} />;
}

/** "תכנון חיסכון לטווח ארוך": a screen of its own (opened from the hub; the FCC card is only a shortcut). Two tabs. Read-only;
 *  nothing here writes (deposits are recorded in the FCC as before). Same server gate as the FCC (flag + canary + owner). */
export function FamilyWealth({ overview, onBack, onRetry }: { overview: OverviewState; onBack: () => void; onRetry: () => void }) {
  const [tab, setTab] = useState<FamilyTabKey>("savings");
  return (
    <main className="ventures-screen fcc-screen">
      <div className="ventures-shell">
        <PageHeader onBack={onBack} title={SCREEN_TITLE} eyebrow="BOSS · אישי"
                    subtitle={overview.status === "ok" ? `נכון ל-${overview.data.as_of}` : undefined} />
        <div className="fcc-stack">
          <FccTabBar active={tab} onChange={setTab} tabs={FAMILY_TABS} idPrefix={FAMILY_TAB_PREFIX} ariaLabel={TABS_ARIA_LABEL} />
          <div role="tabpanel" id={panelId("savings", FAMILY_TAB_PREFIX)} aria-labelledby={tabId("savings", FAMILY_TAB_PREFIX)} hidden={tab !== "savings"}>
            <SavingsSection overview={overview} onRetry={onRetry} />
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

/** The screen as App opens it: loads the FCC overview itself (same endpoint, same gate) — no dependency on the FCC screen being open. */
export function FamilyWealthScreen({ onBack }: { onBack: () => void }) {
  const [state, setState] = useState<OverviewState>({ status: "loading" });
  const load = () => {
    setState({ status: "loading" });
    fetchFccOverview()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", code: (e as { status?: number }).status }));
  };
  useEffect(load, []);
  return <FamilyWealth overview={state} onBack={onBack} onRetry={load} />;
}
