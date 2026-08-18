import { useEffect, useState } from "react";
import { fetchCommandCenter } from "../api";
import {
  actionableApprovalEntries,
  buildDevelopmentList,
  horizonBucketLabel,
  shouldShowFreshness,
  type CompactDevelopmentItem,
} from "../lib/commandCenterPresentation";
import type { CommandCenterAttentionItem, CommandCenterResponse } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

interface Props {
  onBack: () => void;
  onOpenApprovals?: () => void;
  onOpenHealth?: () => void;
  onOpenMarketing?: () => void;
  onOpenVentures?: () => void;
}

type DestinationHandlers = Pick<Props, "onOpenApprovals" | "onOpenHealth" | "onOpenMarketing" | "onOpenVentures">;

type State =
  | { status: "loading" }
  | { status: "ok"; data: CommandCenterResponse }
  | { status: "error"; code?: number; message: string };

const STATE_LABEL: Record<CommandCenterResponse["overall_state"], string> = {
  OK: "הכול תקין לפי המקורות שנבדקו",
  ATTENTION: "יש דברים שדורשים את תשומת הלב שלך",
  PARTIAL: "חלק מהמידע אינו מלא או אינו עדכני",
  UNKNOWN: "לא ניתן לקבוע כרגע את מצב מרכז השליטה",
};

const STATE_TONE: Record<CommandCenterResponse["overall_state"], "neutral" | "success" | "warning" | "danger"> = {
  OK: "success",
  ATTENTION: "danger",
  PARTIAL: "warning",
  UNKNOWN: "neutral",
};

const FRESHNESS_LABEL: Record<string, string> = {
  CURRENT: "עדכני",
  STALE: "דורש רענון",
  PARTIAL: "חלקי",
  UNKNOWN: "לא זמין",
};

const SEVERITY_LABEL: Record<string, string> = {
  INFO: "מידע",
  WARNING: "אזהרה",
  CRITICAL: "קריטי",
};

const DESTINATION_LABEL: Record<string, string> = {
  approvals: "אישורים",
  system_health: "בריאות המערכת",
  marketing: "שיווק",
  ventures: "מיזמים",
};

function freshnessLabel(value: string): string {
  return FRESHNESS_LABEL[value] ?? "מצב לא זמין";
}

function destinationAction(
  destination: string,
  handlers: DestinationHandlers,
): (() => void) | undefined {
  if (destination === "approvals") return handlers.onOpenApprovals;
  if (destination === "system_health") return handlers.onOpenHealth;
  if (destination === "marketing") return handlers.onOpenMarketing;
  if (destination === "ventures") return handlers.onOpenVentures;
  return undefined;
}

function SectionTitle({ title, status }: { title: string; status?: string }) {
  return (
    <div className="command-center-section__heading">
      <h2>{title}</h2>
      {status && shouldShowFreshness(status) && (
        <StatusBadge tone={status === "STALE" ? "warning" : "neutral"}>{freshnessLabel(status)}</StatusBadge>
      )}
    </div>
  );
}

function AttentionCard({ item, handlers }: { item: CommandCenterAttentionItem; handlers: DestinationHandlers }) {
  const action = destinationAction(item.destination, handlers);
  return (
    <div className={`command-center-attention-card command-center-attention-card--${item.severity.toLowerCase()}`}>
      <div className="command-center-card__topline">
        <StatusBadge tone={item.severity === "CRITICAL" ? "danger" : item.severity === "WARNING" ? "warning" : "info"}>
          {SEVERITY_LABEL[item.severity] ?? "מידע"}
        </StatusBadge>
        {DESTINATION_LABEL[item.destination] && <span className="command-center-card__destination">{DESTINATION_LABEL[item.destination]}</span>}
      </div>
      <h3>{item.title}</h3>
      <p>{item.summary}</p>
      {action && <button type="button" className="boss-button boss-button--quiet boss-bubble--action command-center-card__action" onClick={action}>פתיחה</button>}
    </div>
  );
}

const DEVELOPMENT_BADGE_TONE: Record<string, "warning" | "danger" | "success" | "neutral"> = {
  owner_decision: "warning",
  blocked: "danger",
  verification: "warning",
  closed: "success",
};

function developmentBadges(item: CompactDevelopmentItem): { key: string; tone: "warning" | "danger" | "success" | "neutral"; label: string }[] {
  const badges: { key: string; tone: "warning" | "danger" | "success" | "neutral"; label: string }[] = [];
  if (item.owner_decision_required) badges.push({ key: "owner_decision", tone: DEVELOPMENT_BADGE_TONE.owner_decision, label: "דורש החלטה" });
  if (item.blocked) badges.push({ key: "blocked", tone: DEVELOPMENT_BADGE_TONE.blocked, label: "חסום" });
  if (item.needs_verification) badges.push({ key: "verification", tone: DEVELOPMENT_BADGE_TONE.verification, label: "דורש אימות" });
  if (item.closed) badges.push({ key: "closed", tone: DEVELOPMENT_BADGE_TONE.closed, label: "נסגר" });
  if (shouldShowFreshness(item.freshness)) {
    badges.push({ key: "freshness", tone: item.freshness === "STALE" ? "warning" : "neutral", label: freshnessLabel(item.freshness) });
  }
  return badges;
}

function DevelopmentRow({ item, expanded, onToggle }: { item: CompactDevelopmentItem; expanded: boolean; onToggle: () => void }) {
  const badges = developmentBadges(item);
  const hasNextStep = item.next_step.trim() && item.next_step.trim() !== "—";
  return (
    <div className="command-center-development-card">
      <div className="command-center-card__topline">
        <span className="command-center-horizon">{horizonBucketLabel(item.horizon)}</span>
        {badges.length > 0 && (
          <span className="command-center-development-badges">
            {badges.map((badge) => <StatusBadge key={badge.key} tone={badge.tone}>{badge.label}</StatusBadge>)}
          </span>
        )}
      </div>
      <h3>{item.title}</h3>
      <p className="command-center-development-card__clamp">{item.current_stage}</p>
      {hasNextStep && <p className="command-center-development-card__next">הצעד הבא: {item.next_step}</p>}
      <button
        type="button"
        className="boss-button boss-button--quiet boss-bubble--action command-center-development-toggle"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        {expanded ? "סגירת פרטים" : "פרטים"}
      </button>
      {expanded && (
        <div className="command-center-development-details">
          <p><strong>שלב נוכחי: </strong>{item.current_stage}</p>
          <p><strong>הצעד הבא שהוחלט: </strong>{hasNextStep ? item.next_step : "אין צעד מוחלט כרגע"}</p>
          <p><strong>מצב ראיות: </strong>{item.evidence_state}</p>
          <p><strong>מצב עבודה: </strong>{item.work_state}</p>
          <p><strong>עודכן לאחרונה: </strong>{item.last_reconciled}</p>
        </div>
      )}
    </div>
  );
}

function Unavailable({ text }: { text: string }) {
  return <p className="command-center-unavailable">{text}</p>;
}

export function OwnerControlCenter({ onBack, onOpenApprovals, onOpenHealth, onOpenMarketing, onOpenVentures }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attentionExpanded, setAttentionExpanded] = useState(false);
  const [expandedDevelopment, setExpandedDevelopment] = useState<Set<string>>(new Set());

  function load() {
    setState({ status: "loading" });
    fetchCommandCenter()
      .then((data) => setState({ status: "ok", data }))
      .catch((error: unknown) => {
        const typed = error as Error & { status?: number };
        setState({ status: "error", code: typed.status, message: typed.message });
      });
  }

  useEffect(() => { load(); }, []);

  if (state.status === "loading") {
    return (
      <main className="ventures-screen command-center-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} title="מרכז השליטה" eyebrow="BOSS" subtitle="תמונה תמציתית לקריאה, הבנה והחלטה" />
          <ScreenState state="loading" title="טוען את מרכז השליטה" message="אוסף את התמונה הקנונית…" />
          <div className="command-center-skeleton" aria-hidden="true"><span /><span /><span /></div>
        </div>
      </main>
    );
  }

  if (state.status === "error") {
    const forbidden = state.code === 401 || state.code === 403;
    return (
      <main className="ventures-screen command-center-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} title="מרכז השליטה" eyebrow="BOSS" />
          <ScreenState state="error" title={forbidden ? "אין הרשאה לצפות במרכז השליטה" : "לא הצלחנו לטעון את מרכז השליטה"} message={forbidden ? "המסך זמין לבעלים בלבד." : "אפשר לנסות שוב בעוד רגע."} action={<button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>נסו שוב</button>} />
        </div>
      </main>
    );
  }

  const data = state.data;
  const visibleAttentionItems = attentionExpanded ? data.attention.items : data.attention.items.slice(0, 3);
  const systemState = data.system_status.state;
  const pendingEntries = actionableApprovalEntries(data.pending_decisions);
  const developmentItems = buildDevelopmentList(data.development_status);
  const handlers = { onOpenApprovals, onOpenHealth, onOpenMarketing, onOpenVentures };

  function toggleDevelopmentItem(key: string) {
    setExpandedDevelopment((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  return (
    <main className="ventures-screen command-center-screen">
      <div className="ventures-shell">
        <PageHeader onBack={onBack} title="מרכז השליטה" eyebrow="BOSS" subtitle="תמונה תמציתית לקריאה, הבנה והחלטה" action={<button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={load}>רענון</button>} badge={<StatusBadge tone={STATE_TONE[data.overall_state]}>{STATE_LABEL[data.overall_state]}</StatusBadge>} />

        <div className="command-center-stack">
          <section className="command-center-hero" aria-labelledby="attention-heading">
            <SectionTitle title="דורש תשומת לב עכשיו" status={data.freshness.attention} />
            {data.attention.items.length ? <><div className="command-center-attention-list">{visibleAttentionItems.map((item) => <AttentionCard key={item.signal_key} item={item} handlers={handlers} />)}</div>{data.attention.items.length > 3 && <button type="button" className="boss-button boss-button--quiet boss-bubble--action command-center-more" aria-expanded={attentionExpanded} onClick={() => setAttentionExpanded((expanded) => !expanded)}>{attentionExpanded ? "הצג פחות" : "הצג עוד"}</button>}</> : data.freshness.attention === "CURRENT" ? <p id="attention-heading" className="command-center-positive">אין כרגע דברים דחופים שדורשים את תשומת לבך.</p> : <Unavailable text="לא ניתן לקבוע כרגע מה דורש תשומת לב." />}
          </section>

          {pendingEntries.length > 0 && (
            <Surface className="command-center-section" aria-labelledby="pending-heading">
              <SectionTitle title="החלטות ממתינות" status={data.freshness.attention} />
              <div className="command-center-decision-list" id="pending-heading">{pendingEntries.map((item) => <AttentionCard key={item.signal_key} item={item} handlers={handlers} />)}</div>
            </Surface>
          )}

          <Surface className="command-center-section" aria-labelledby="development-heading">
            <div className="command-center-section__heading">
              <SectionTitle title="מצב הפיתוח" status={data.freshness.development} />
              {developmentItems.length > 0 && (
                <div className="command-center-development-controls">
                  <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setExpandedDevelopment(new Set(developmentItems.map((item) => item.initiative_key)))}>פתח הכול</button>
                  <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setExpandedDevelopment(new Set())}>סגור הכול</button>
                </div>
              )}
            </div>
            {data.development_status.projection_state === "UNKNOWN" ? (
              <div id="development-heading"><Unavailable text="מצב הפיתוח אינו זמין כרגע." /></div>
            ) : developmentItems.length === 0 ? (
              <p id="development-heading" className="command-center-positive">אין יוזמות פעילות להצגה כרגע.</p>
            ) : (
              <div className="command-center-development-list" id="development-heading">
                {developmentItems.map((item) => (
                  <DevelopmentRow
                    key={item.initiative_key}
                    item={item}
                    expanded={expandedDevelopment.has(item.initiative_key)}
                    onToggle={() => toggleDevelopmentItem(item.initiative_key)}
                  />
                ))}
              </div>
            )}
          </Surface>

          {systemState !== "UNKNOWN" && (
            <Surface className="command-center-section command-center-section--compact" aria-labelledby="system-heading">
              <SectionTitle title="מצב המערכת" status={data.freshness.system_status} />
              <div className="command-center-inline-status">
                <StatusBadge tone={systemState === "CURRENT" ? "success" : "danger"}>{systemState === "CURRENT" ? "תקין" : "דורש תשומת לב"}</StatusBadge>
                {onOpenHealth && <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onOpenHealth}>פתיחת בריאות המערכת</button>}
              </div>
            </Surface>
          )}
        </div>
      </div>
    </main>
  );
}
