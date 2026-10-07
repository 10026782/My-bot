import { useEffect, useRef, useState } from "react";
import { fetchFccOverview, postFccWrite } from "../api";
import type { FccGoalRow, FccLoans, FccOverview, FccTurn } from "../types";
import { CATEGORY_LABEL, goalCardModel, headerCards, money } from "../lib/fccPresentation";
import {
  FILTERS, RANK_MODES, STATUS_UNKNOWN, compareRows, filterLoans, loanCardModel, loanGoalModel, loanHeaderCards, sortLoans,
  type LoanFilter, type RankMode,
} from "../lib/fccLoans";
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

const GOAL_STATUS: Record<FccGoalRow["status"], { label: string; tone: "info" | "success" | "danger" | "warning" | "neutral" }> = {
  in_progress: { label: "בדרך", tone: "info" },
  achieved: { label: "הושג", tone: "success" },
  overdue: { label: "באיחור", tone: "danger" },
  missing_target: { label: "חסר יעד", tone: "warning" },
  project: { label: "פעיל", tone: "info" },
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

const ACTION_WORDS = { confirm: "אשר", edit: "ערוך", cancel: "בטל" } as const;

function QuickUpdate({ initial, onDone }: { initial: FccTurn | null; onDone: () => void }) {
  const [text, setText] = useState("");
  const [turn, setTurn] = useState<FccTurn | null>(initial);
  const [lastText, setLastText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);
  const turnRef = useRef<HTMLElement | null>(null);
  // התשובה מוצגת מעל תיבת הכתיבה ודוחפת אותה למטה — מגלגלים אליה כדי שלא תיעלם מחוץ למסך
  useEffect(() => { turnRef.current?.scrollIntoView?.({ block: "start", behavior: "smooth" }); }, [turn, receipt, error]);

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

  // במובייל: לחיצה על הכפתור גורמת ל-blur של התיבה → המקלדת נסגרת, הפריסה זזה והקליק אובד. שומרים את הפוקוס.
  const keepKeyboard = (e: { preventDefault: () => void }) => e.preventDefault();
  const submit = () => {
    const value = text.trim();
    if (!turn) setLastText(value);
    void send({ text: value });
  };
  const open = turn && ["ask", "unrelated", "review", "needs_goal", "confirmed", "partial_failure"].includes(turn.state);
  const reviewing = turn?.state === "review";

  return (
    <section className="fcc-section" aria-labelledby="fcc-quick-heading" ref={turnRef}>
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
                disabled={busy || !text.trim()} onClick={submit}
                onPointerDown={keepKeyboard} onMouseDown={keepKeyboard}>
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
  const model = goalCardModel(goal);
  return (
    <div className={`fcc-goal fcc-goal--${model.kind}`}>
      <div className="fcc-goal__topline">
        <StatusBadge tone={st.tone}>{st.label}</StatusBadge>
        {goal.category && <StatusBadge tone="neutral">{CATEGORY_LABEL[goal.category] ?? goal.category}</StatusBadge>}
      </div>
      <h3>{goal.title}</h3>
      {model.progressPct != null && (
        <div className="fcc-goal__bar" role="progressbar" aria-valuenow={model.progressPct} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ inlineSize: `${model.progressPct}%` }} />
        </div>
      )}
      {model.metrics.length > 0 && (
        <dl className="fcc-goal__grid">
          {model.metrics.map((m) => (
            <div key={m.label}><dt>{m.label}</dt><dd>{m.value}</dd></div>
          ))}
        </dl>
      )}
      {(model.kind === "needs_target" || (model.kind === "numeric" && model.note)) && <p className="fcc-goal__note">{model.note}</p>}
      {model.sourceNote && <p className="fcc-goal__note">{model.sourceNote}</p>}
      {model.kind === "project" && (
        <dl className="fcc-goal__grid fcc-goal__grid--project">
          <div>
            <dt>פעולה הבאה</dt>
            <dd>{model.nextAction ? `${model.nextAction.title}${model.nextAction.due ? ` · ${model.nextAction.due}` : ""}` : "חסרה פעולה הבאה"}</dd>
          </div>
          {model.targetDate && <div><dt>תאריך יעד</dt><dd>{model.targetDate}</dd></div>}
        </dl>
      )}
    </div>
  );
}

function LoansSection({ loans }: { loans: FccLoans }) {
  const [filter, setFilter] = useState<LoanFilter>("all");
  const [mode, setMode] = useState<RankMode>("high_interest");
  const [picked, setPicked] = useState<string[]>([]);
  const visible = sortLoans(filterLoans(loans.items, filter), loans, mode);
  const goal = loanGoalModel(loans);
  const byId = (id: string) => loans.items.find((l) => l.id === id);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 2 ? [p[1], id] : [...p, id]));
  const a = picked[0] ? byId(picked[0]) : undefined;
  const b = picked[1] ? byId(picked[1]) : undefined;

  return (
    <section className="fcc-section" aria-labelledby="fcc-loans-heading">
      <h2 id="fcc-loans-heading" className="fcc-section__heading">הלוואות וחוב</h2>
      {loans.summary.total_active_loans === 0 ? (
        <ScreenState state="empty" title="אין הלוואות פעילות" message="הלוואות נרשמות בטבלת Loans." />
      ) : (
        <div className="fcc-stack">
          <div className="fcc-kpis">
            {loanHeaderCards(loans).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}
          </div>
          {loans.summary.unknown_status_count > 0 && (
            <p className="fcc-goal__note">{loans.summary.unknown_status_count} הלוואות עם {STATUS_UNKNOWN} (Active Loan לא מסומן) — כלולות בסיכומים.</p>
          )}
          {goal && (
            <Surface variant="subtle" padding="compact">
              <dl className="fcc-goal__grid">
                {goal.lines.map((m) => <div key={m.label}><dt>{m.label}</dt><dd>{m.value}</dd></div>)}
              </dl>
            </Surface>
          )}
          <div className="fcc-chips" role="tablist" aria-label="סוג הלוואה">
            {FILTERS.map((f) => (
              <button key={f.key} type="button" role="tab" aria-selected={filter === f.key}
                      className={`boss-button boss-bubble--action ${filter === f.key ? "boss-button--primary" : "boss-button--quiet"}`}
                      onClick={() => setFilter(f.key)}>{f.label}</button>
            ))}
          </div>
          <div className="fcc-chips" role="group" aria-label="סדר תצוגה">
            {RANK_MODES.map((m) => (
              <button key={m.key} type="button" aria-pressed={mode === m.key}
                      className={`boss-button boss-bubble--action ${mode === m.key ? "boss-button--primary" : "boss-button--quiet"}`}
                      onClick={() => setMode(m.key)}>{m.label}</button>
            ))}
          </div>
          {visible.length === 0 ? (
            <ScreenState state="empty" title="אין הלוואות בסוג הזה" />
          ) : (
            <div className="fcc-list">
              {visible.map((l) => {
                const m = loanCardModel(l);
                return (
                  <div key={l.id} className="fcc-goal fcc-loan">
                    <div className="fcc-goal__topline">
                      <StatusBadge tone={l.loan_type ? "neutral" : "warning"}>{m.typeLabel}</StatusBadge>
                      {m.statusUnknown && <StatusBadge tone="warning">{STATUS_UNKNOWN}</StatusBadge>}
                      {m.incomplete && <StatusBadge tone="warning">נתונים חלקיים</StatusBadge>}
                    </div>
                    <h3>{m.title}{m.lender && <span className="fcc-loan__lender"> · {m.lender}</span>}</h3>
                    {m.assetLine && <p className="fcc-goal__note">{m.assetLine}</p>}
                    <dl className="fcc-goal__grid">
                      {m.rows.map((r) => <div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}
                    </dl>
                    <p className="fcc-goal__note">{m.freedLine}</p>
                    <button type="button" className="boss-button boss-button--quiet boss-bubble--action" aria-pressed={picked.includes(l.id)}
                            onClick={() => toggle(l.id)}>{picked.includes(l.id) ? "הסר מההשוואה" : "השווה"}</button>
                  </div>
                );
              })}
            </div>
          )}
          {a && b ? (
            <Surface className="fcc-compare" aria-label="השוואת הלוואות">
              <table className="fcc-compare__table">
                <thead><tr><th></th><th>{a.name}</th><th>{b.name}</th></tr></thead>
                <tbody>
                  {compareRows(a, b).map((r) => <tr key={r.label}><th scope="row">{r.label}</th><td>{r.a}</td><td>{r.b}</td></tr>)}
                </tbody>
              </table>
              <p className="fcc-goal__note">ההשוואה מציגה נתונים בלבד — ההחלטה שלך.</p>
            </Surface>
          ) : picked.length === 1 ? <p className="fcc-goal__note">בחר הלוואה נוספת להשוואה.</p> : null}
        </div>
      )}
    </section>
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
  return shell(
    <div className="fcc-stack">
      <div className="fcc-kpis">
        {headerCards(data).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}
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

      {data.loans && <LoansSection loans={data.loans} />}

      <section className="fcc-section" aria-labelledby="fcc-recent-heading">
        <h2 id="fcc-recent-heading" className="fcc-section__heading">התקדמות אחרונה</h2>
        {data.recent_events.length === 0 ? (
          <ScreenState state="empty" title="אין אירועים עדיין" />
        ) : (
          <div className="fcc-list">
            {data.recent_events.map((e, i) => (
              <div key={i} className="fcc-event">
                <span>{e["Occurred At"]}</span>
                <strong>{e.Kind === "target_change" ? `יעד חדש ${money(e.Amount)}` : e.Kind === "direct_cost" ? `-${money(e.Amount)}` : money(e.Amount)}</strong>
                {e.Kind === "direct_cost" && <StatusBadge tone="warning">הוצאה ישירה</StatusBadge>}
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
