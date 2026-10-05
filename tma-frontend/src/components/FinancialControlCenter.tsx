import { useEffect, useState } from "react";
import { fetchFccOverview, postFccWrite } from "../api";
import type { FccGoalRow, FccOverview, FccSummaryCard, FccWritePlan } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: FccOverview }
  | { status: "error"; code?: number };

const nf = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 });
const money = (n: number | null | undefined) => (n == null ? "—" : `₪${nf.format(n)}`);

const CATEGORY_LABEL: Record<string, string> = {
  income: "הכנסה", savings: "חיסכון", debt: "חוב", debt_repaid: "חוב", emergency_fund: "קרן חירום",
};

const GOAL_STATUS: Record<FccGoalRow["status"], { label: string; tone: "info" | "success" | "danger" | "warning" }> = {
  in_progress: { label: "בדרך", tone: "info" },
  achieved: { label: "הושג", tone: "success" },
  overdue: { label: "באיחור", tone: "danger" },
  missing_target: { label: "חסר יעד", tone: "warning" },
};

function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Surface variant="subtle" padding="compact" className="fcc-kpi">
      <p className="fcc-kpi__value">{value}</p>
      <p className="fcc-kpi__label">{label}</p>
      {hint && <p className="fcc-kpi__hint">{hint}</p>}
    </Surface>
  );
}

function cardPair(card: FccSummaryCard | undefined, empty = "לא הוגדר יעד") {
  return card ? { value: `${money(card.actual)} / ${money(card.target)}`, hint: undefined } : { value: "—", hint: empty };
}

function QuickUpdate({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<FccWritePlan | null>(null);
  const [goalId, setGoalId] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);

  const run = async (confirm: boolean, chosen?: string) => {
    if (busy || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await postFccWrite({ text: text.trim(), goal_id: chosen ?? goalId, confirm });
      if (result.status === "executed") {
        setReceipt("העדכון נרשם ✓");
        setPlan(null);
        setText("");
        setGoalId(undefined);
        onDone();
      } else {
        setPlan(result);
        if (result.status === "partial_failure") setError("הפעולה לא הושלמה במלואה — בדקו ונסו שוב.");
      }
    } catch (e) {
      setError((e as Error).message || "הפעולה נכשלה");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="fcc-section" aria-labelledby="fcc-quick-heading">
      <h2 id="fcc-quick-heading" className="fcc-section__heading">עדכון מהיר</h2>
      <Surface className="fcc-quick">
        <textarea
          className="fcc-quick__input"
          rows={2}
          value={text}
          placeholder="כתוב עדכון כלכלי…"
          aria-label="עדכון כלכלי"
          onChange={(e) => { setText(e.target.value); setPlan(null); setReceipt(null); setGoalId(undefined); }}
        />
        <button type="button" className="boss-button boss-button--primary boss-bubble--action"
                disabled={busy || !text.trim()} onClick={() => run(false)}>
          {busy ? "בודק…" : "תצוגה מקדימה"}
        </button>

        {plan?.status === "preview" && (
          <div className="fcc-quick__preview" role="status">
            <p>{plan.summary}</p>
            <button type="button" className="boss-button boss-button--primary boss-bubble--action"
                    disabled={busy} onClick={() => run(true)}>
              אשר ורשום
            </button>
          </div>
        )}
        {plan?.status === "needs_goal" && (
          <div className="fcc-quick__preview" role="status">
            <p>{plan.message}</p>
            <div className="fcc-quick__choices">
              {(plan.candidates ?? []).map((c) => (
                <button key={c.goal_id} type="button" className="boss-button boss-button--quiet boss-bubble--action"
                        disabled={busy} onClick={() => { setGoalId(c.goal_id); run(false, c.goal_id); }}>
                  {c.title}
                </button>
              ))}
            </div>
          </div>
        )}
        {plan && ["duplicate", "clarify", "denied"].includes(plan.status) && (
          <p className="fcc-quick__note" role="status">{plan.message}</p>
        )}
        {receipt && <p className="fcc-quick__receipt" role="status">{receipt}</p>}
        {error && <p className="fcc-quick__error" role="alert">⚠️ {error}</p>}
      </Surface>
    </section>
  );
}

function GoalCard({ goal }: { goal: FccGoalRow }) {
  const st = GOAL_STATUS[goal.status];
  const pct = goal.target ? Math.min(100, Math.round((goal.actual / goal.target) * 100)) : 0;
  return (
    <div className="fcc-goal">
      <div className="fcc-goal__topline">
        <StatusBadge tone={st.tone}>{st.label}</StatusBadge>
        {goal.category && <StatusBadge tone="neutral">{CATEGORY_LABEL[goal.category] ?? goal.category}</StatusBadge>}
      </div>
      <h3>{goal.title}</h3>
      <div className="fcc-goal__bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ inlineSize: `${pct}%` }} />
      </div>
      <dl className="fcc-goal__grid">
        <div><dt>יעד</dt><dd>{money(goal.target)}</dd></div>
        <div><dt>בפועל</dt><dd>{money(goal.actual)}</dd></div>
        <div><dt>נשאר</dt><dd>{money(goal.remaining)}</dd></div>
        <div><dt>יעד דינמי לשבוע</dt><dd>{money(goal.dynamic_target_per_week)}</dd></div>
      </dl>
    </div>
  );
}

export function FinancialControlCenter({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  const load = () => {
    setState({ status: "loading" });
    fetchFccOverview()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", code: (e as { status?: number }).status }));
  };
  useEffect(load, []);

  const shell = (children: React.ReactNode, subtitle?: string) => (
    <main className="ventures-screen fcc-screen">
      <div className="ventures-shell">
        <PageHeader
          onBack={onBack}
          title="המרכז הכלכלי"
          eyebrow="BOSS · אישי"
          subtitle={subtitle}
          action={<button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={load}>רענון</button>}
        />
        {children}
      </div>
    </main>
  );

  if (state.status === "loading") {
    return shell(<ScreenState state="loading" title="טוען את המרכז הכלכלי" message="אוסף את התמונה העדכנית…" />);
  }
  if (state.status === "error") {
    const unavailable = state.code === 404;
    const forbidden = state.code === 401 || state.code === 403;
    return shell(
      <ScreenState
        state="error"
        title={unavailable ? "המסך עדיין לא פעיל" : forbidden ? "אין הרשאה" : "לא הצלחנו לטעון"}
        message={unavailable ? "המרכז הכלכלי טרם הופעל." : forbidden ? "המסך אישי ונגיש לבעל הרשומה בלבד." : "אפשר לנסות שוב בעוד רגע."}
        action={!unavailable && !forbidden && (
          <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>נסו שוב</button>
        )}
      />,
    );
  }

  const { data } = state;
  const income = cardPair(data.summary.income);
  const savings = cardPair(data.summary.savings);
  const debt = cardPair(data.summary.debt);
  const emergency = cardPair(data.summary.emergency_fund);
  const weekly = data.summary.income?.dynamic_target_per_week;

  return shell(
    <div className="fcc-stack">
      <div className="fcc-kpis">
        <KpiCard label="הכנסה מול יעד" value={income.value} hint={income.hint} />
        <KpiCard label="יעד דינמי לשבוע" value={weekly != null ? money(weekly) : "—"} />
        <KpiCard label="חיסכון" value={savings.value} hint={savings.hint} />
        <KpiCard label="חוב שנפרע" value={debt.value} hint={debt.hint} />
        <KpiCard label="שיפור תזרים חודשי" value={money(data.monthly_cash_improvement)} />
        <KpiCard label="קרן חירום" value={emergency.value}
                 hint={data.summary.emergency_fund ? "כיסוי חודשים: אין נתוני הוצאה" : emergency.hint} />
      </div>

      <QuickUpdate onDone={load} />

      <section className="fcc-section" aria-labelledby="fcc-tasks-heading">
        <h2 id="fcc-tasks-heading" className="fcc-section__heading">דורש פעולה</h2>
        {data.tasks.length === 0 ? (
          <ScreenState state="empty" title="אין משימות פתוחות" message="אין פעולות המשך כלכליות כרגע." />
        ) : (
          <div className="fcc-list">
            {data.tasks.map((t) => (
              <div key={t.id} className="fcc-task">
                <h3>{t.title}</h3>
                {t.due_date && <p>📅 {t.due_date}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="fcc-section" aria-labelledby="fcc-goals-heading">
        <h2 id="fcc-goals-heading" className="fcc-section__heading">יעדים</h2>
        {data.goals.length === 0 ? (
          <ScreenState state="empty" title="אין יעדים פעילים" message="כתבו בעדכון המהיר ״תוסיף יעד חדש …״ כדי להתחיל." />
        ) : (
          <div className="fcc-list">{data.goals.map((g) => <GoalCard key={g.goal_id} goal={g} />)}</div>
        )}
      </section>

      <section className="fcc-section" aria-labelledby="fcc-recent-heading">
        <h2 id="fcc-recent-heading" className="fcc-section__heading">התקדמות אחרונה</h2>
        {data.recent_events.length === 0 ? (
          <ScreenState state="empty" title="אין אירועים עדיין" />
        ) : (
          <div className="fcc-list">
            {data.recent_events.map((e, i) => (
              <div key={i} className="fcc-event">
                <span>{e["Occurred At"]}</span>
                <strong>{e.Kind === "target_change" ? `יעד חדש ${money(e.Amount)}` : money(e.Amount)}</strong>
                {e.Kind === "monthly_recurring" && <StatusBadge tone="info">חודשי קבוע</StatusBadge>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>,
    `נכון ל-${data.as_of}`,
  );
}
