import { useEffect, useState } from "react";
import { fetchFccOverview, postFccWrite } from "../api";
import type { FccGoalRow, FccOverview, FccSummaryCard, FccTurn } from "../types";
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

const ACTION_WORDS = { confirm: "אשר", edit: "ערוך", cancel: "בטל" } as const;

function QuickUpdate({ initial, onDone }: { initial: FccTurn | null; onDone: () => void }) {
  const [text, setText] = useState("");
  const [turn, setTurn] = useState<FccTurn | null>(initial);
  const [lastText, setLastText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);

  const send = async (body: { text: string; goal_id?: string }) => {
    if (busy || !body.text.trim()) return;
    setBusy(true);
    setError(null);
    setReceipt(null);
    try {
      const result = await postFccWrite(body);
      if (result.state === "executed") {
        setReceipt(result.message || "נרשם ✓");
        setTurn(null);
        setLastText("");
        onDone();
      } else if (result.state === "cancelled") {
        setReceipt(result.message);
        setTurn(null);
      } else {
        setTurn(result);
        if (result.state === "partial_failure") setError(result.message);
      }
      setText("");
    } catch (e) {
      setError((e as Error).message || "הפעולה נכשלה");
    } finally {
      setBusy(false);
    }
  };

  const submit = () => {
    const value = text.trim();
    if (!turn) setLastText(value);
    void send({ text: value });
  };
  const open = turn && ["ask", "review", "needs_goal", "confirmed", "partial_failure"].includes(turn.state);
  const reviewing = turn?.state === "review";

  return (
    <section className="fcc-section" aria-labelledby="fcc-quick-heading">
      <h2 id="fcc-quick-heading" className="fcc-section__heading">עדכון מהיר</h2>
      <Surface className="fcc-quick">
        {turn && (
          <div className="fcc-quick__turn" role="status">
            <p className="fcc-quick__message">{turn.message}</p>
            {turn.state === "needs_goal" && (
              <div className="fcc-quick__choices">
                {(turn.candidates ?? []).map((c) => (
                  <button key={c.goal_id} type="button" className="boss-button boss-button--quiet boss-bubble--action"
                          disabled={busy} onClick={() => void send({ text: lastText || c.title || "", goal_id: c.goal_id })}>
                    {c.title}
                  </button>
                ))}
              </div>
            )}
            {reviewing && (
              <div className="fcc-quick__choices">
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={busy}
                        onClick={() => void send({ text: ACTION_WORDS.confirm })}>אשר ורשום</button>
                <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                        onClick={() => void send({ text: ACTION_WORDS.edit })}>ערוך</button>
              </div>
            )}
            {open && (
              <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                      onClick={() => void send({ text: ACTION_WORDS.cancel })}>בטל</button>
            )}
          </div>
        )}
        <textarea
          className="fcc-quick__input"
          rows={2}
          value={text}
          placeholder={open ? "ענה כאן…" : "כתוב עדכון כלכלי…"}
          aria-label="עדכון כלכלי"
          onChange={(e) => setText(e.target.value)}
        />
        <button type="button" className="boss-button boss-button--primary boss-bubble--action"
                disabled={busy || !text.trim()} onClick={submit}>
          {busy ? "בודק…" : open ? "שלח" : "שלח עדכון"}
        </button>
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

      <QuickUpdate initial={data.draft} onDone={load} />

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
          <ScreenState state="empty" title="אין יעדים פעילים" message="כתבו בעדכון המהיר, למשל: ״תוסיף יעד קרן חירום 60000 מצטבר עד סוף השנה״." />
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
