import { useEffect, useRef, useState } from "react";
import { fetchFccAccounts, fetchFccOverview, postFccAccountsForecast } from "../api";
import type { FccAccount, FccAccountsForecast, FccAccountsView, FccOverview } from "../types";
import { LineChart } from "./PortfolioLabCharts";
import { DEFAULT_FORECAST_FORM, FAMILY_TABS, FAMILY_TAB_PREFIX, FORECAST_NOTE, FORECAST_TITLE, NO_ACCOUNTS_MESSAGE, NO_ACCOUNTS_TITLE, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, accountsTabModel, familyCardModel, forecastModel, forecastParams, savingsTabModel, type FamilyTabKey, type ForecastForm } from "../lib/familyWealth";
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

type AccountsState = { status: "loading" } | { status: "ok"; data: FccAccountsView } | { status: "error"; code?: number };

export function AccountsPanel({ state, onRetry }: { state: AccountsState; onRetry: () => void }) {
  if (state.status === "loading") return <ScreenState state="loading" title="טוען את החשבונות" message="אוסף את היתרות האחרונות…" />;
  if (state.status === "error") {
    const closed = state.code === 404, forbidden = state.code === 401 || state.code === 403;
    return (
      <ScreenState state="error" title={closed ? "המסך עדיין לא פעיל" : forbidden ? "אין הרשאה" : "לא הצלחנו לטעון"}
                   message={closed ? "החשבונות אינם זמינים בחשבון הזה." : forbidden ? "החשבונות אישיים ונגישים לבעל הרשומה בלבד." : "אפשר לנסות שוב בעוד רגע."}
                   action={!closed && !forbidden && (
                     <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={onRetry}>נסו שוב</button>
                   )} />
    );
  }
  const m = accountsTabModel(state.data);
  if (!m.hasAccounts) return <ScreenState state="empty" title={NO_ACCOUNTS_TITLE} message={NO_ACCOUNTS_MESSAGE} />;
  return (
    <div className="fcc-stack">
      <div className="fcc-kpis">
        <KpiCard label={m.total.label} value={m.total.value} hint={m.total.hint} />
        {m.extras.map((r) => <KpiCard key={r.key} label={r.label} value={r.value} hint={r.hint} />)}
      </div>
      <ul className="fcc-stack" aria-label="רשימת חשבונות">
        {m.rows.map((r) => (
          <li key={r.id}>
            <Surface variant="subtle" padding="compact" className="fcc-kpi" aria-label={r.title}>
              <p className="fcc-kpi__label">{r.title}{r.closed ? " · סגור" : ""}</p>
              {r.subtitle && <p className="fcc-kpi__hint">{r.subtitle}</p>}
              <p className="fcc-kpi__value">{r.value}</p>
              <p className="fcc-kpi__hint">{r.hint}</p>
              {r.estimate && <p className="fcc-kpi__hint">{r.estimate}</p>}
            </Surface>
          </li>
        ))}
      </ul>
      {m.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
      <ForecastSection accounts={state.data.accounts.filter((a) => a.status !== "closed" && a.balance)} />
    </div>
  );
}

type ForecastState = { status: "idle" } | { status: "loading" } | { status: "ok"; view: FccAccountsForecast } | { status: "error"; message: string; code?: number };

/** A1: assumptions -> POST /api/fcc/accounts/forecast -> render. Runs only when asked; every number shown is the server's engine result. */
function ForecastSection({ accounts }: { accounts: FccAccount[] }) {
  const [form, setForm] = useState<ForecastForm>(DEFAULT_FORECAST_FORM);
  const [state, setState] = useState<ForecastState>({ status: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const latest = useRef(0);
  if (accounts.length === 0) return null;
  const set = <K extends keyof ForecastForm>(key: K, value: ForecastForm[K]) => setForm((f) => ({ ...f, [key]: value }));
  const run = () => {
    const parsed = forecastParams(form);
    if (!parsed.ok) { setFormError(parsed.error); return; }
    setFormError(null);
    const id = ++latest.current;                       // a slower, older answer must never overwrite a newer one
    setState({ status: "loading" });
    postFccAccountsForecast(parsed.params)
      .then((view) => { if (id === latest.current) setState({ status: "ok", view }); })
      .catch((e: Error & { status?: number }) => { if (id === latest.current) setState({ status: "error", message: e.message, code: e.status }); });
  };
  return (
    <section className="fcc-section" aria-labelledby="fw-forecast">
      <h2 id="fw-forecast" className="fcc-section__heading">{FORECAST_TITLE}</h2>
      <p className="fcc-goal__note">{FORECAST_NOTE}</p>
      <form className="pl-form" onSubmit={(e) => { e.preventDefault(); run(); }} aria-label="הנחות התחזית">
        <div className="pl-grid">
          <label>מספר שנים (10–100)<input inputMode="numeric" value={form.years} onChange={(e) => set("years", e.target.value)} /></label>
          <label>תשואה שנתית ברוטו (%)<input inputMode="decimal" value={form.returnPct} onChange={(e) => set("returnPct", e.target.value)} /></label>
          <label>דמי ניהול ברירת מחדל (%)<input inputMode="decimal" value={form.feePct} onChange={(e) => set("feePct", e.target.value)} /></label>
          <label>אינפלציה שנתית (%)<input inputMode="decimal" value={form.inflationPct} onChange={(e) => set("inflationPct", e.target.value)} /></label>
        </div>
        <fieldset>
          <legend>הפקדה חודשית לכל חשבון (₪, אופציונלי)</legend>
          <div className="pl-grid">
            {accounts.map((a) => (
              <label key={a.id}>{a.name || "חשבון ללא שם"}
                <input inputMode="decimal" placeholder="0" value={form.deposits[a.id] ?? ""}
                       onChange={(e) => set("deposits", { ...form.deposits, [a.id]: e.target.value })} />
              </label>
            ))}
          </div>
        </fieldset>
        <button type="submit" className="boss-button boss-button--primary boss-bubble--action" disabled={state.status === "loading"}>
          {state.status === "loading" ? "מחשב…" : "חשב תחזית"}
        </button>
        {formError && <p className="fcc-quick__error" role="alert">⚠️ {formError}</p>}
      </form>
      {state.status === "loading" && <ScreenState state="loading" title="מחשב" message="המנוע מריץ את התחזית…" />}
      {state.status === "error" && (
        <ScreenState state="error" title={state.code === 404 ? "המסך עדיין לא פעיל" : state.code === 429 ? "יותר מדי חישובים" : "החישוב נכשל"}
                     message={state.code === 404 ? "התחזית אינה זמינה בחשבון הזה." : state.code === 429 ? "אפשר לנסות שוב בעוד דקה." : state.message} />
      )}
      {state.status === "ok" && <ForecastResult view={state.view} />}
    </section>
  );
}

export function ForecastResult({ view }: { view: FccAccountsForecast }) {
  const m = forecastModel(view);
  return (
    <div className="fcc-stack">
      <div className="fcc-kpis">{m.total.map((r) => <KpiCard key={r.key} label={r.label} value={r.value} hint={r.hint} />)}</div>
      {m.chart && <Surface padding="compact"><LineChart model={m.chart} xLabel="שנים" title="תחזית מאוחדת" /></Surface>}
      {m.rows.length > 0 && (
        <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
          <thead><tr>{m.head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{m.rows.map((r) => <tr key={r.id}>{r.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""} title={i === 3 ? r.feeHint : undefined}>{c}</td>)}</tr>)}</tbody>
        </table></div></Surface>
      )}
      <ul className="pl-list pl-list--small" dir="auto">{m.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}

/** Own call, own states; mounted only when the tab is opened (nothing is fetched in the background). */
function AccountsSection() {
  const [state, setState] = useState<AccountsState>({ status: "loading" });
  const load = () => {
    setState({ status: "loading" });
    fetchFccAccounts()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", code: (e as { status?: number }).status }));
  };
  useEffect(load, []);
  return <AccountsPanel state={state} onRetry={load} />;
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
          {/* accounts: read-only list + consolidated value; its own fetch, mounted only when opened */}
          <div role="tabpanel" id={panelId("accounts", FAMILY_TAB_PREFIX)} aria-labelledby={tabId("accounts", FAMILY_TAB_PREFIX)} hidden={tab !== "accounts"}>
            {tab === "accounts" && <AccountsSection />}
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
