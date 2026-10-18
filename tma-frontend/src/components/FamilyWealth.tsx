import { useEffect, useRef, useState } from "react";
import { fetchFccAccounts, fetchFccOverview, postFccAccountsForecast, postFccFundingPlan, postFccFundingSave } from "../api";
import type { FccAccount, FccAccountsForecast, FccAccountsView, FccOverview, FundingPlan, FundingRequestBody } from "../types";
import { LineChart } from "./PortfolioLabCharts";
import { ALLOCATION_NOTE, DEFAULT_FUNDING_FORM, FUNDING_ADDABLE, FUNDING_FIELDS, FUNDING_INTRO, FUNDING_PRINCIPLE, FUNDING_TITLE, FUNDING_TYPE_LABELS, fundingModel, fundingRequest, newFundingOption, type FundingForm, type FundingOptionDraft, ALLOCATION_TITLE, NO_ALLOCATIONS_MESSAGE, type AllocationModel, DEFAULT_FORECAST_FORM, FAMILY_TABS, FAMILY_TAB_PREFIX, FORECAST_NOTE, FORECAST_TITLE, NO_ACCOUNTS_MESSAGE, NO_ACCOUNTS_TITLE, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, accountsTabModel, familyCardModel, forecastModel, forecastParams, savingsTabModel, type FamilyTabKey, type ForecastForm } from "../lib/familyWealth";
import { ACCOUNTS_COMPOSER, FUNDING_COMPOSER, panelId, tabId } from "../lib/fccTabs";
import { ContextualComposer, FccTabBar, useFccWriter } from "./FccTabBar";
import { FUNDING_SAVE_NOTE } from "../lib/familyWealth";
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

type SavingsData = Pick<FccOverview, "summary" | "savings_release" | "savings_history" | "as_of" | "goals" | "assets" | "loans">;
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
          <tbody>{m.rows.map((r) => <tr key={r.id}>{r.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""} title={i === 3 ? r.feeHint : i === 0 ? r.liquidity || undefined : undefined}>{c}</td>)}</tr>)}</tbody>
        </table></div></Surface>
      )}
      {m.goals.length > 0 && (
        <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
          <caption dir="auto">כיסוי מטרות — פוטנציאלי בלבד, לפי ״נגיש מאומת״, בערך נומינלי בסוף החודש האחרון שהושלם עד תאריך היעד (כסף שהופקד אחריו לא נספר). אותו כסף עשוי להופיע בכמה מטרות.</caption>
          <thead><tr>{m.goalHead.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{m.goals.map((g) => <tr key={g.id}>{g.cells.map((c, i) => <td key={i} className={i && i < g.cells.length - 1 ? "pl-num" : ""}>{c}</td>)}</tr>)}</tbody>
        </table></div></Surface>
      )}
      <AllocationsBlock model={m.allocations} present={view.allocations !== undefined} />
      <ul className="pl-list pl-list--small" dir="auto">{m.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}

/** B2: what the owner allocated per account and per goal, split by liquidity — every number is the server's, nothing is computed here. */
function AllocationsBlock({ model, present }: { model: AllocationModel | null; present: boolean }) {
  if (!present) return null;
  if (!model) return <p className="fcc-goal__note" dir="auto">{NO_ALLOCATIONS_MESSAGE}</p>;
  return (
    <section className="fcc-section" aria-labelledby="fw-allocations">
      <h3 id="fw-allocations" className="fcc-section__heading">{ALLOCATION_TITLE}</h3>
      <p className="fcc-goal__note" dir="auto">{ALLOCATION_NOTE}</p>
      <div className="fcc-kpis">{model.kpis.map((r) => <KpiCard key={r.key} label={r.label} value={r.value} hint={r.hint} />)}</div>
      {model.accounts.length > 0 && (
        <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
          <caption dir="auto">לפי חשבון</caption>
          <thead><tr>{model.accountHead.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{model.accounts.map((a) => <tr key={a.id} className={a.over ? "pl-row--warn" : undefined}>{a.cells.map((c, i) => <td key={i} className={i > 0 && i < 4 ? "pl-num" : ""}>{c}</td>)}</tr>)}</tbody>
        </table></div></Surface>
      )}
      {model.goals.length > 0 && (
        <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
          <caption dir="auto">לפי מטרה — מה שהוקצה, מפוצל לפי נזילות החשבון המקצה. כסף מותנה או נעול אינו נחשב נגיש.</caption>
          <thead><tr>{model.goalHead.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{model.goals.map((g) => (
            <tr key={g.id}>{g.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""} title={i === 0 && g.warn ? g.warn : undefined}>{i === 0 && g.warn ? `${c} ⚠ ${g.warn}` : c}</td>)}</tr>
          ))}</tbody>
        </table></div></Surface>
      )}
      <ul className="pl-list pl-list--small" dir="auto">{model.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </section>
  );
}

type FundingState = { status: "idle" } | { status: "loading" } | { status: "ok"; plan: FundingPlan; goalId: string; titles: Record<string, string>; body: FundingRequestBody } | { status: "error"; message: string; code?: number };

/** Goal Funding Planner (step 1b): a goal -> typed funding options -> POST /api/fcc/funding/plan -> a neutral comparison. Runs only when asked; the page
 *  converts typed text to numbers once on submit and shows only what the server returns (no ranking, no recommendation, no client arithmetic). */
export function FundingSection({ overview }: { overview: OverviewState }) {
  const [form, setForm] = useState<FundingForm>(DEFAULT_FUNDING_FORM);
  const [accounts, setAccounts] = useState<FccAccount[]>([]);
  const [state, setState] = useState<FundingState>({ status: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const counter = useRef(0);
  const latest = useRef(0);
  const [selected, setSelected] = useState<string[]>([]);
  const writer = useFccWriter(null, "funding", () => undefined);
  useEffect(() => { fetchFccAccounts().then((v) => setAccounts(v.accounts.filter((a) => a.status !== "closed"))).catch(() => setAccounts([])); }, []);
  if (overview.status === "loading") return <ScreenState state="loading" title="טוען את היעדים" message="אוסף את התמונה העדכנית…" />;
  if (overview.status === "error") return <ScreenState state="error" title={overview.code === 404 ? "המסך עדיין לא פעיל" : "לא הצלחנו לטעון"} message="היעדים אינם זמינים כרגע." />;
  const data = overview.data;
  const goals = (data.goals ?? []).filter((g) => g.target != null && g.end_date != null && g.mode !== "project");
  const lookups = {
    accounts: accounts.map((a) => ({ value: a.id, label: a.name || "חשבון ללא שם" })),
    assets: (data.assets?.items ?? []).map((a) => ({ value: a.id, label: a.name || "נכס ללא שם" })),
    receivables: (data.loans?.items ?? []).filter((l) => l.direction === "owed_to_me" && l.active).map((l) => ({ value: l.id, label: l.name || "חוב ללא שם" })),
    deposit_options: form.options.filter((o) => o.type === "new_deposits").map((o, i) => ({ value: o.id, label: `${FUNDING_TYPE_LABELS[o.type]} #${i + 1}` })),
  };
  const setOption = (id: string, patch: Partial<FundingOptionDraft>) => setForm((f) => ({ ...f, options: f.options.map((o) => (o.id === id ? { ...o, ...patch } : o)) }));
  const setValue = (o: FundingOptionDraft, key: string, value: string) => setOption(o.id, { values: { ...o.values, [key]: value } });
  const titles = () => {
    const seen: Record<string, number> = {};
    return Object.fromEntries(form.options.map((o) => {
      seen[o.type] = (seen[o.type] ?? 0) + 1;
      const base = o.type === "custom" && o.values.label?.trim() ? o.values.label.trim() : FUNDING_TYPE_LABELS[o.type];
      return [o.id, form.options.filter((x) => x.type === o.type).length > 1 ? `${base} #${seen[o.type]}` : base];
    }));
  };
  const run = () => {
    const parsed = fundingRequest(form);
    if (!parsed.ok) { setFormError(parsed.error); return; }
    setFormError(null);
    const id = ++latest.current;                       // a slower, older answer must never overwrite a newer one
    const goalId = form.goalId, names = titles();
    setState({ status: "loading" });
    setSelected([]);
    writer.dismiss();
    postFccFundingPlan(parsed.body)
      .then((plan) => { if (id === latest.current) setState({ status: "ok", plan, goalId, titles: names, body: parsed.body }); })
      .catch((e: Error & { status?: number }) => { if (id === latest.current) setState({ status: "error", message: e.message, code: e.status }); });
  };
  const model = state.status === "ok" ? fundingModel(state.plan, state.goalId, state.titles) : null;
  return (
    <section className="fcc-section" aria-labelledby="fw-funding">
      <h2 id="fw-funding" className="fcc-section__heading">{FUNDING_TITLE}</h2>
      <p className="fcc-goal__note" dir="auto">{FUNDING_INTRO}</p>
      <p className="fcc-goal__note" dir="auto">{FUNDING_PRINCIPLE}</p>
      <form className="pl-form" onSubmit={(e) => { e.preventDefault(); run(); }} aria-label="יעד ואפשרויות מימון">
        {goals.length === 0 ? (
          <ScreenState state="empty" title="אין יעד עם סכום ותאריך" message="הגדירו יעד (למשל חתונה של ילד) עם סכום ותאריך במרכז הכלכלי." />
        ) : (
          <label>יעד
            <select value={form.goalId} onChange={(e) => setForm((f) => ({ ...f, goalId: e.target.value }))}>
              <option value="">בחרו יעד…</option>
              {goals.map((g) => <option key={g.goal_id} value={g.goal_id}>{g.title || "מטרה ללא שם"}</option>)}
            </select>
          </label>
        )}
        <div className="pl-grid">
          <label>תשואה שנתית ברירת מחדל (%)<input inputMode="decimal" value={form.returnPct} onChange={(e) => setForm((f) => ({ ...f, returnPct: e.target.value }))} /></label>
          <label>דמי ניהול ברירת מחדל (%)<input inputMode="decimal" value={form.feePct} onChange={(e) => setForm((f) => ({ ...f, feePct: e.target.value }))} /></label>
          <label>אינפלציה שנתית (%)<input inputMode="decimal" value={form.inflationPct} onChange={(e) => setForm((f) => ({ ...f, inflationPct: e.target.value }))} /></label>
        </div>
        {form.options.map((o) => (
          <fieldset key={o.id} className="fw-option-form">
            <legend>{FUNDING_TYPE_LABELS[o.type]}</legend>
            <div className="pl-grid">
              {FUNDING_FIELDS[o.type].filter((f) => !f.when || f.when(o.values)).map((f) => {
                const v = o.values[f.key] ?? "";
                if (f.kind === "bool") {
                  return <label key={f.key} className="pl-check"><input type="checkbox" checked={v === "true"} onChange={(e) => setValue(o, f.key, e.target.checked ? "true" : "")} />{f.label}</label>;
                }
                if (f.kind === "select") {
                  const choices = f.options ?? (f.optionsFrom ? lookups[f.optionsFrom] : []);
                  return (
                    <label key={f.key}>{f.label}
                      <select value={v} onChange={(e) => setValue(o, f.key, e.target.value)}>
                        {!f.required || !v ? <option value="">{f.required ? "בחרו…" : "ללא"}</option> : null}
                        {choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                      </select>
                    </label>
                  );
                }
                return (
                  <label key={f.key}>{f.label}
                    <input type={f.kind === "date" ? "date" : "text"} inputMode={f.kind === "number" ? "decimal" : undefined} value={v} onChange={(e) => setValue(o, f.key, e.target.value)} />
                    {f.hint && <small>{f.hint}</small>}
                  </label>
                );
              })}
              <label>סכום לשימוש בתוכנית (₪, אופציונלי)<input inputMode="decimal" value={o.use} onChange={(e) => setOption(o.id, { use: e.target.value })} /></label>
            </div>
            <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setForm((f) => ({ ...f, options: f.options.filter((x) => x.id !== o.id) }))}>הסר אפשרות</button>
          </fieldset>
        ))}
        <div className="fw-add" role="group" aria-label="הוספת אפשרות מימון">
          {FUNDING_ADDABLE.map((t) => (
            <button key={t} type="button" className="boss-button boss-button--quiet boss-bubble--action"
                    onClick={() => setForm((f) => ({ ...f, options: [...f.options, newFundingOption(t, ++counter.current)] }))}>＋ {FUNDING_TYPE_LABELS[t]}</button>
          ))}
        </div>
        <button type="submit" className="boss-button boss-button--primary boss-bubble--action" disabled={state.status === "loading" || goals.length === 0}>
          {state.status === "loading" ? "משווה…" : "השווה אפשרויות"}
        </button>
        {formError && <p className="fcc-quick__error" role="alert">⚠️ {formError}</p>}
      </form>
      {state.status === "loading" && <ScreenState state="loading" title="משווה" message="המנוע מחשב את האפשרויות…" />}
      {state.status === "error" && (
        <ScreenState state="error" title={state.code === 404 ? "המסך עדיין לא פעיל" : state.code === 429 ? "יותר מדי חישובים" : "ההשוואה נכשלה"}
                     message={state.code === 404 ? "ההשוואה אינה זמינה בחשבון הזה." : state.code === 429 ? "אפשר לנסות שוב בעוד דקה." : state.message} />
      )}
      {model && <FundingResult model={model} selection={{ selected, onToggle: (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id])) }} />}
      {model && state.status === "ok" && (
        <div className="fcc-stack">
          <p className="fcc-goal__note" dir="auto">{FUNDING_SAVE_NOTE}</p>
          <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={selected.length === 0 || writer.busy || writer.turn != null}
                  onClick={() => void writer.open(() => postFccFundingSave(state.body, selected))}>שמירת תוכנית</button>
          {(writer.turn || writer.receipt || writer.error) && (
            <ContextualComposer config={FUNDING_COMPOSER} turn={writer.turn} receipt={writer.receipt} error={writer.error} busy={writer.busy}
                                targets={{ goals: [], loans: [], assets: [] }}
                                onStart={() => undefined} onSend={(t, g) => void writer.send(t, g)} onDismiss={writer.dismiss} />
          )}
        </div>
      )}
    </section>
  );
}

function Rows({ rows }: { rows: { label: string; value: string }[] }) {
  return <dl className="fw-rows">{rows.map((r) => <div key={r.label} className="fw-rows__row"><dt>{r.label}</dt><dd dir="auto">{r.value}</dd></div>)}</dl>;
}

/** The server's comparison, in the server's order (fixed by option type — never by outcome). Nothing is highlighted as better. */
export function FundingResult({ model, selection }: { model: NonNullable<ReturnType<typeof fundingModel>>; selection?: { selected: string[]; onToggle: (id: string) => void } }) {
  return (
    <div className="fcc-stack" aria-label="השוואת אפשרויות מימון">
      <Surface padding="compact">
        <h3 className="fcc-section__heading">{model.needTitle}</h3>
        <Rows rows={model.needRows} />
        {model.needReason && <p className="fcc-goal__note" dir="auto">{model.needReason}</p>}
      </Surface>
      {model.options.map((o) => (
        <Surface key={o.id} padding="compact" className="fw-option" aria-label={o.title}>
          <h3 className="fcc-section__heading">{o.title}</h3>
          {selection && o.feasible !== false && (
            <label className="pl-check"><input type="checkbox" checked={selection.selected.includes(o.id)} onChange={() => selection.onToggle(o.id)} />לשמור באפשרויות התוכנית</label>
          )}
          <p className="fw-badges"><span className="fw-badge">{o.verdict}</span><span className="fw-badge">ודאות: {o.certainty}</span></p>
          <Rows rows={o.rows} />
          {o.lists.map((l) => <div key={l.label}><p className="fcc-goal__note">{l.label}:</p><ul className="pl-list pl-list--small" dir="auto">{l.items.map((i) => <li key={i}>{i}</li>)}</ul></div>)}
          {o.note && <p className="fcc-goal__note" dir="auto">{o.note}</p>}
        </Surface>
      ))}
      {model.plan && (
        <Surface padding="compact" aria-label="התוכנית שהוזנה">
          <h3 className="fcc-section__heading">התוכנית שהוזנה — מפוצלת לפי ודאות</h3>
          <Rows rows={model.plan.rows} />
          <ul className="pl-list pl-list--small" dir="auto">{model.plan.allocations.map((a) => <li key={a}>{a}</li>)}</ul>
          <p className="fcc-goal__note" dir="auto">{model.plan.note}</p>
        </Surface>
      )}
      {model.portfolio && <Surface padding="compact" aria-label="מבט תיק"><h3 className="fcc-section__heading">מבט תיק</h3><Rows rows={model.portfolio.rows} /></Surface>}
      <ul className="pl-list pl-list--small" dir="auto">{model.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
    </div>
  );
}

/** Own call, own states; mounted only when the tab is opened (nothing is fetched in the background). The two account actions (D1 step 8) run in
 *  the shared contextual composer: a chip only names the intent + the account, the server asks / reviews / waits for "אשר"; a landed write reloads. */
function AccountsSection() {
  const [state, setState] = useState<AccountsState>({ status: "loading" });
  const load = () => {
    setState({ status: "loading" });
    fetchFccAccounts()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", code: (e as { status?: number }).status }));
  };
  useEffect(load, []);
  const refresh = () => { fetchFccAccounts().then((data) => setState({ status: "ok", data })).catch(() => undefined); };
  const writer = useFccWriter(null, "accounts", refresh);
  const editable = state.status === "ok" ? state.data.accounts.filter((a) => a.status !== "closed") : [];
  return (
    <div className="fcc-stack">
      {editable.length > 0 && (
        <ContextualComposer config={ACCOUNTS_COMPOSER} turn={writer.turn} receipt={writer.receipt} error={writer.error} busy={writer.busy}
                            targets={{ goals: [], loans: [], assets: [], accounts: editable.map((a) => ({ id: a.id, title: a.name || "חשבון ללא שם" })) }}
                            onStart={(i, id) => void writer.start(i, id)} onSend={(t, g) => void writer.send(t, g)} onDismiss={writer.dismiss} />
      )}
      <AccountsPanel state={state} onRetry={load} />
    </div>
  );
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
          {/* funding planner: mounted only when opened; the comparison runs on demand, never in the background */}
          <div role="tabpanel" id={panelId("funding", FAMILY_TAB_PREFIX)} aria-labelledby={tabId("funding", FAMILY_TAB_PREFIX)} hidden={tab !== "funding"}>
            {tab === "funding" && <FundingSection overview={overview} />}
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
