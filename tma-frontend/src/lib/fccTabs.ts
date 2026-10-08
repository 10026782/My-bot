// Tabs of the Financial Control Center. Pure: no fetching, no storage. The last-used tab is remembered only in this
// module's memory (i.e. while the app stays open); a fresh open of the app always starts on "התנהלות חודשית".
import type { FccTurn } from "../types";

export type FccTabKey = "monthly" | "loans" | "assets";

export const FCC_TABS: { key: FccTabKey; label: string }[] = [
  { key: "monthly", label: "התנהלות חודשית" },
  { key: "loans", label: "הלוואות וחוב" },
  { key: "assets", label: "נכסים והון" },
];

export const DEFAULT_TAB: FccTabKey = "monthly";

let remembered: FccTabKey | null = null;

export const isTab = (v: unknown): v is FccTabKey => FCC_TABS.some((t) => t.key === v);
export const initialTab = (): FccTabKey => (remembered && isTab(remembered) ? remembered : DEFAULT_TAB);
export function rememberTab(key: FccTabKey): void { if (isTab(key)) remembered = key; }
/** A new app session starts from the default again (also used by tests). */
export function resetTabMemory(): void { remembered = null; }

export const tabId = (key: FccTabKey): string => `fcc-tab-${key}`;
export const panelId = (key: FccTabKey): string => `fcc-panel-${key}`;

/** Keyboard model of the tab strip (WAI-ARIA tabs): arrows move to the neighbouring tab (wrapping), Home/End jump to the
 *  ends. The visual order is mirrored in RTL, so "next" is ArrowLeft there. Returns null for any other key. */
export function tabForKey(current: FccTabKey, key: string, rtl: boolean): FccTabKey | null {
  const i = FCC_TABS.findIndex((t) => t.key === current);
  const last = FCC_TABS.length - 1;
  if (i < 0) return null;
  if (key === "Home") return FCC_TABS[0].key;
  if (key === "End") return FCC_TABS[last].key;
  const step = key === "ArrowRight" ? (rtl ? -1 : 1) : key === "ArrowLeft" ? (rtl ? 1 : -1) : 0;
  return step ? FCC_TABS[(i + step + FCC_TABS.length) % FCC_TABS.length].key : null;
}

// ── Contextual composer (one writer engine on the server, one draft slot; each tab only changes its title and chips) ──
/** A chip only names an intent (+ which kind of record it is about when that record must be chosen first). It never
 *  writes: the server opens the draft (POST /api/fcc/intent/start) and the usual review -> אשר flow follows. */
export interface ComposerChip { intent: string; label: string; pick?: "goal" | "loan" | "asset" }
export interface ComposerConfig {
  title: string;
  chips: ComposerChip[];
  freeText: boolean;     // free text may open a NEW draft here (monthly only); an open draft can always be answered
  hint: string;
}

export const COMPOSER: Record<FccTabKey, ComposerConfig> = {
  monthly: {
    title: "עדכון כספי",
    chips: [
      { intent: "monthly.income", label: "+ הכנסה" },
      { intent: "monthly.household_expense", label: "+ הוצאה ביתית" },
      { intent: "monthly.direct_cost", label: "+ עלות ישירה" },
      { intent: "monthly.obligation", label: "+ התחייבות" },
      { intent: "monthly.goal_update", label: "+ עדכון יעד", pick: "goal" },
    ],
    freeText: true,
    hint: "אפשר גם לכתוב חופשי.",
  },
  loans: {
    title: "עדכון הלוואה",
    chips: [
      { intent: "loan.update_balance", label: "עדכון יתרה", pick: "loan" },
      { intent: "loan.update_payment", label: "שינוי החזר", pick: "loan" },
      { intent: "loan.create", label: "הלוואה חדשה" },
      { intent: "loan.close", label: "סגירת הלוואה", pick: "loan" },
    ],
    freeText: false,
    hint: "בחרו פעולה — המערכת תשאל רק מה שחסר.",
  },
  assets: {
    title: "עדכון נכס",
    chips: [
      { intent: "asset.update_value", label: "עדכון שווי", pick: "asset" },
      { intent: "asset.update_mortgage", label: "עדכון משכנתא", pick: "asset" },
      { intent: "asset.next_step", label: "פעולה הבאה", pick: "asset" },
    ],
    freeText: false,
    hint: "בחרו פעולה — המערכת תשאל רק מה שחסר. סימון נכס כנמכר יתווסף בשלב הבא.",
  },
};

export const WRITER_WORDS = { confirm: "אשר", edit: "ערוך", cancel: "בטל" } as const;

export interface WriterView {
  message: string;
  confirm: string | null;                      // label of the confirm button (also the retry after a partial failure)
  canEdit: boolean;
  showInput: boolean;                          // the server asks something / waits for an edit
  cancelsDraft: boolean;                       // "בטל" must reach the server (an open draft exists)
  choices: { goal_id: string; title: string }[];   // the server asks WHICH of the caller's own goals
  dismissOnly: boolean;                        // terminal info: nothing pending, just clear the message
}

/** What the composer shows for the server's latest turn. Pure: the client renders, the server decides. */
export function writerView(turn: FccTurn | null, receipt: string | null): WriterView {
  const base: WriterView = { message: receipt ?? turn?.message ?? "", confirm: null, canEdit: false, showInput: false, cancelsDraft: false, choices: [], dismissOnly: true };
  if (receipt || !turn) return base;
  switch (turn.state) {
    case "review":
      return { ...base, confirm: "אשר ורשום", canEdit: true, cancelsDraft: true, dismissOnly: false };
    case "ask":
    case "unrelated":
      return { ...base, showInput: true, cancelsDraft: true, dismissOnly: false };
    case "needs_goal":
      return { ...base, showInput: true, cancelsDraft: true, dismissOnly: false,
               choices: (turn.candidates ?? []).map((c) => ({ goal_id: c.goal_id, title: c.title ?? "" })) };
    case "confirmed":
      return { ...base, cancelsDraft: true, dismissOnly: false };
    case "partial_failure":
      return { ...base, confirm: "נסה שוב", cancelsDraft: true, dismissOnly: false };
    default:                                   // info / denied / duplicate / clarify / cancelled: nothing pending on the client
      return base;
  }
}

/** The one input box: an open question is always answerable; a NEW free-text draft only where the tab allows it. */
export function inputVisible(cfg: ComposerConfig, view: WriterView, pickingIntent: boolean): boolean {
  if (pickingIntent) return false;
  return view.showInput || (cfg.freeText && view.dismissOnly);
}

/** Chips are disabled while any draft is open (one shared slot) — the open turn is shown instead. */
export const chipsEnabled = (view: WriterView, busy: boolean): boolean => !busy && view.dismissOnly;

/** Next writer state after a server turn. ``refresh`` = the writes landed, so the overview must be reloaded. */
export function nextWriterState(result: FccTurn): { turn: FccTurn | null; receipt: string | null; refresh: boolean } {
  if (result.state === "executed") return { turn: null, receipt: result.message || "נרשם ✓", refresh: true };
  if (result.state === "cancelled") return { turn: null, receipt: result.message || null, refresh: false };
  return { turn: result, receipt: null, refresh: false };
}
