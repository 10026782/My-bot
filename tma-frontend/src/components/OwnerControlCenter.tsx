import { useEffect, useState } from "react";
import { fetchCommandCenter } from "../api";
import type {
  CommandCenterAttentionItem,
  CommandCenterDevelopmentItem,
  CommandCenterResponse,
} from "../types";
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
      {status && <StatusBadge tone={status === "CURRENT" ? "success" : status === "STALE" ? "warning" : "neutral"}>{freshnessLabel(status)}</StatusBadge>}
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

function DevelopmentCard({ item }: { item: CommandCenterDevelopmentItem }) {
  return (
    <div className="command-center-development-card">
      <div className="command-center-card__topline">
        <span className="command-center-horizon">{item.horizon}</span>
        <StatusBadge tone={item.freshness === "CURRENT" ? "success" : item.freshness === "STALE" ? "warning" : "neutral"}>{freshnessLabel(item.freshness)}</StatusBadge>
      </div>
      <h3>{item.title}</h3>
      <p>{item.current_stage}</p>
      {item.next_step && item.next_step !== "—" && <p className="command-center-development-card__next">הצעד הבא: {item.next_step}</p>}
    </div>
  );
}

function DevelopmentGroup({ title, items, empty }: { title: string; items: CommandCenterDevelopmentItem[]; empty?: string }) {
  return (
    <div className="command-center-development-group">
      <h3>{title}</h3>
      {items.length ? items.map((item) => <DevelopmentCard key={item.initiative_key} item={item} />) : <p className="command-center-muted">{empty ?? "אין פריטים להצגה"}</p>}
    </div>
  );
}

function Unavailable({ text }: { text: string }) {
  return <p className="command-center-unavailable">{text}</p>;
}

export function OwnerControlCenter({ onBack, onOpenApprovals, onOpenHealth, onOpenMarketing, onOpenVentures }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

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
  const attentionItems = data.attention.items.slice(0, 3);
  const pendingUnknown = data.pending_decisions.length === 0 && data.freshness.attention !== "CURRENT";
  const systemState = data.system_status.state;
  const development = data.development_status;
  const handlers = { onOpenApprovals, onOpenHealth, onOpenMarketing, onOpenVentures };
  const moreAttentionAction = data.attention.items.slice(3).map((item) => destinationAction(item.destination, handlers)).find(Boolean);

  return (
    <main className="ventures-screen command-center-screen">
      <div className="ventures-shell">
        <PageHeader onBack={onBack} title="מרכז השליטה" eyebrow="BOSS" subtitle="תמונה תמציתית לקריאה, הבנה והחלטה" action={<button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={load}>רענון</button>} badge={<StatusBadge tone={STATE_TONE[data.overall_state]}>{STATE_LABEL[data.overall_state]}</StatusBadge>} />

        <div className="command-center-stack">
          <section className="command-center-hero" aria-labelledby="attention-heading">
            <SectionTitle title="דורש תשומת לב עכשיו" status={data.freshness.attention} />
            {attentionItems.length ? <><div className="command-center-attention-list">{attentionItems.map((item) => <AttentionCard key={item.signal_key} item={item} handlers={handlers} />)}</div>{moreAttentionAction && <button type="button" className="boss-button boss-button--quiet boss-bubble--action command-center-more" onClick={moreAttentionAction}>הצג עוד</button>}</> : data.freshness.attention === "CURRENT" ? <p id="attention-heading" className="command-center-positive">אין כרגע דברים דחופים שדורשים את תשומת לבך.</p> : <Unavailable text="לא ניתן לקבוע כרגע מה דורש תשומת לב." />}
          </section>

          <Surface className="command-center-section" aria-labelledby="pending-heading"><SectionTitle title="החלטות ממתינות" status={data.freshness.attention} />{pendingUnknown ? <Unavailable text="מצב ההחלטות אינו זמין כרגע." /> : data.pending_decisions.length ? <div className="command-center-decision-list">{data.pending_decisions.slice(0, 3).map((item) => <AttentionCard key={item.signal_key} item={item} handlers={handlers} />)}</div> : <p id="pending-heading" className="command-center-positive">אין החלטות ממתינות כרגע.</p>}</Surface>

          <Surface className="command-center-section" aria-labelledby="business-heading"><SectionTitle title="מצב העסק" status={data.freshness.business_status} />{data.business_status.state === "CURRENT" ? <p id="business-heading" className="command-center-positive">מצב העסק זמין.</p> : <Unavailable text="מצב עסקי מאוחד עדיין אינו מחובר למקור קנוני." />}</Surface>

          <Surface className="command-center-section" aria-labelledby="development-heading"><SectionTitle title="מצב הפיתוח" status={data.freshness.development} />{development.projection_state === "UNKNOWN" ? <Unavailable text="מצב הפיתוח אינו זמין כרגע." /> : <div className="command-center-development-grid" id="development-heading"><DevelopmentGroup title="עובדים עכשיו" items={development.current_focus} /><DevelopmentGroup title="הצעד הבא" items={development.next_actions} /><DevelopmentGroup title="דורש אימות" items={development.needs_verification} /><DevelopmentGroup title="חסום / דורש החלטה" items={[...development.blocked, ...development.owner_decisions]} /><DevelopmentGroup title="נסגר לאחרונה" items={development.recently_closed} /></div>}</Surface>

          <Surface className="command-center-section command-center-section--compact" aria-labelledby="system-heading"><SectionTitle title="מצב המערכת" status={data.freshness.system_status} /><div className="command-center-inline-status"><StatusBadge tone={systemState === "CURRENT" ? "success" : systemState === "ATTENTION" ? "danger" : "neutral"}>{systemState === "CURRENT" ? "תקין" : systemState === "ATTENTION" ? "דורש תשומת לב" : "מידע לא זמין"}</StatusBadge>{onOpenHealth && <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onOpenHealth}>פתיחת בריאות המערכת</button>}</div></Surface>

          <Surface className="command-center-section command-center-section--compact" aria-labelledby="activity-heading"><SectionTitle title="פעילות אחרונה" status={data.freshness.recent_activity} /><Unavailable text="פעילות אחרונה עדיין אינה מחוברת למקור קנוני." /></Surface>
        </div>
      </div>
    </main>
  );
}
