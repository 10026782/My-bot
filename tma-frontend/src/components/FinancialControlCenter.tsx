import { useState, useEffect } from "react";
import { fetchFccLoanScenario, fetchFccOverview, postFccIntent, postFccWrite } from "../api";
import type { FccGoalRow, FccOverview, FccTurn } from "../types";
import { CATEGORY_LABEL, goalCardModel, goalPickLabel, headerCards, money } from "../lib/fccPresentation";
import { KpiCard, SavingsFollowUp, SavingsReleaseCard } from "./FccKpiCard";
import { AssetsSection, NextActionPrompt } from "./FccAssets";
import { ASSET_GONE } from "../lib/fccAssets";
import { LoansSection } from "./FccLoans";
import { ContextualComposer, FccTabBar } from "./FccTabBar";
import { initialTab, nextWriterState, panelId, rememberTab, tabId, type FccTabKey } from "../lib/fccTabs";
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

/** The single shared writer state (one draft slot per person): the composer in every tab renders THIS, so a half-finished
 *  draft is never forked by a tab switch. All logic is the server's; this only calls it and keeps the latest turn. */
function useFccWriter(initial: FccTurn | null, tab: FccTabKey, onDone: () => void) {
  const [turn, setTurn] = useState<FccTurn | null>(initial);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [followUp, setFollowUp] = useState(false);
  const [followUpAsset, setFollowUpAsset] = useState<string | null>(null);
  // the overview (and a draft opened in chat) arrives after the first render: adopt it unless this screen is already showing something
  useEffect(() => { if (initial && !turn && !receipt) setTurn(initial); }, [initial]);   // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (call: () => Promise<FccTurn>) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await call();
      const next = nextWriterState(result);
      setTurn(next.turn);
      setReceipt(next.receipt);
      if (result.state === "partial_failure") setError(result.message);
      setFollowUp(result.state === "executed" && result.follow_up === "savings");
      setFollowUpAsset(result.state === "executed" ? result.follow_up_asset ?? null : null);
      if (next.refresh) onDone();
    } catch (e) {
      setError((e as Error).message || "הפעולה נכשלה");
    } finally {
      setBusy(false);
    }
  };
  const start = (intent: string, entityId?: string) => run(async () => {
    const result = await postFccIntent(intent, entityId);
    if (result.state !== "info" || !result.entity) return result;
    // another draft is already open: show IT (the server's own latest turn) instead of a dead-end message
    const open = await fetchFccOverview().then((o) => o.draft).catch(() => null);
    return open ?? result;
  });
  const send = (text: string, goalId?: string) => run(() => postFccWrite({ text, scope: tab, ...(goalId ? { goal_id: goalId } : {}) }));
  const dismiss = () => { setTurn(null); setReceipt(null); setError(null); };
  return { turn, receipt, error, busy, start, send, dismiss, followUp, clearFollowUp: () => setFollowUp(false),
           followUpAsset, clearFollowUpAsset: () => setFollowUpAsset(null) };
}

function GoalCard({ goal, onUpdate, disabled }: { goal: FccGoalRow; onUpdate: (goalId: string) => void; disabled: boolean }) {
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
      <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-goal__update" disabled={disabled}
              onClick={() => onUpdate(goal.goal_id)}>עדכן יעד</button>
    </div>
  );
}

export function FinancialControlCenter({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [tab, setTab] = useState<FccTabKey>(initialTab);       // remembered while the app stays open; a fresh open starts on "monthly"
  const changeTab = (key: FccTabKey) => { rememberTab(key); setTab(key); };

  const load = () => {
    setState({ status: "loading" });
    fetchFccOverview()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", code: (e as { status?: number }).status }));
  };
  useEffect(load, []);
  // refresh without the loading state: the loans tab keeps its closing receipt on screen while the numbers update
  const refresh = () => { fetchFccOverview().then((data) => setState({ status: "ok", data })).catch(() => undefined); };
  const writer = useFccWriter(state.status === "ok" ? state.data.draft : null, tab, refresh);

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
  const monthly = (
    <div className="fcc-stack">
      <div className="fcc-kpis">
        {headerCards(data).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}
      </div>

      {data.savings_release && (
        <SavingsReleaseCard release={data.savings_release} onStart={(i) => void writer.start(i)} disabled={writer.busy || writer.turn != null} />
      )}

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
          <div className="fcc-list">{data.goals.map((g) => <GoalCard key={g.goal_id} goal={g} disabled={writer.busy || writer.turn != null}
                                                          onUpdate={(id) => void writer.start("monthly.goal_update", id)} />)}</div>
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
                <strong>{e.Kind === "target_change" ? `יעד חדש ${money(e.Amount)}` : e.Kind === "direct_cost" ? `-${money(e.Amount)}` : money(e.Amount)}</strong>
                {e.Kind === "direct_cost" && <StatusBadge tone="warning">הוצאה ישירה</StatusBadge>}
                {e.Kind === "monthly_recurring" && <StatusBadge tone="info">חודשי קבוע</StatusBadge>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
  const targets = {
    goals: data.goals.map((g) => ({ id: g.goal_id, title: goalPickLabel(g) })),
    assets: (data.assets?.items ?? []).filter((a) => !ASSET_GONE.includes(a.status ?? "")).map((a) => ({ id: a.id, title: a.name ?? "" })),
    loans: (data.loans?.items ?? []).filter((l) => l.active).map((l) => ({ id: l.id, title: `${l.name ?? ""}${l.direction === "owed_to_me" ? " (חייב לי)" : ""}` })),
  };
  const panels: Record<FccTabKey, React.ReactNode> = {
    monthly,
    loans: data.loans ? <LoansSection loans={data.loans} loadScenario={fetchFccLoanScenario}
                                                actions={{ onAction: (intent, id) => void writer.start(intent, id), disabled: writer.busy || writer.turn != null }} /> : <ScreenState state="empty" title="אין נתוני הלוואות" />,
    assets: data.assets ? <AssetsSection assets={data.assets} actions={{ onAction: (intent, id) => void writer.start(intent, id), disabled: writer.busy || writer.turn != null }} /> : <ScreenState state="empty" title="אין נתוני נכסים" />,
  };
  return shell(
    <div className="fcc-stack">
      <FccTabBar active={tab} onChange={changeTab} />
      <ContextualComposer tab={tab} turn={writer.turn} receipt={writer.receipt} error={writer.error} busy={writer.busy}
                          targets={targets} onStart={(i, id) => void writer.start(i, id)} onSend={(t, g) => void writer.send(t, g)}
                          onDismiss={writer.dismiss} />
      {writer.followUpAsset && writer.turn == null && (
        <NextActionPrompt assets={data.assets} assetId={writer.followUpAsset} onAdd={(id) => void writer.start("asset.next_step", id)}
                          onDismiss={writer.clearFollowUpAsset} disabled={writer.busy} />
      )}
      {writer.followUp && writer.turn == null && (
        <SavingsFollowUp release={data.savings_release} onStart={(i) => void writer.start(i)} onDismiss={writer.clearFollowUp}
                         disabled={writer.busy} />
      )}
      {/* all panels stay mounted (hidden when inactive) so a half-typed update, the loans filter or the budget input survive a tab switch */}
      {(Object.keys(panels) as FccTabKey[]).map((key) => (
        <div key={key} role="tabpanel" id={panelId(key)} aria-labelledby={tabId(key)} hidden={tab !== key}>{panels[key]}</div>
      ))}
    </div>,
    `נכון ל-${data.as_of}`,
  );
}
