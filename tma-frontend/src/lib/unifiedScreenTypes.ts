// Stage A0 of the unified family-wealth screen (docs/portfolio_lab/UNIFIED_SCREEN_IMPLEMENTATION_PLAN.md): the TYPE CONTRACT only.
// No runtime code, no logic, no fetching, no money arithmetic. Stages A (model), C (copy) and B1 (component) are written against these types.
// Every number a card shows is the server's, passed through unchanged; "missing" is `null` + a reason, never 0.
import type { FccNetWorth, FccOverview, FundingPlan, PaceView } from "../types";

/** The five cards, in the order the owner reads them (the model, not this file, fixes the order):
 *  net worth (C2) -> accumulation pace (C4) -> goals (incl. future_goal) -> funding sources -> gap to close the goal. */
export type UnifiedCardKey = "net_worth" | "pace" | "goals" | "funding_sources" | "gap";

/** `loading`: request in flight. `ready`: complete. `partial`: shown, but the server flagged gaps. `missing`: no data to show (say what to enter).
 *  `unavailable`: the endpoint failed or answered 404 — the other cards keep working. */
export type UnifiedCardStatus = "loading" | "ready" | "partial" | "missing" | "unavailable";

/** How sure a figure is. Only `reported` and `stale` may ever sit under "what exists"; the rest are shown apart and never summed with it. */
export type UnifiedCertainty = "reported" | "stale" | "conditional" | "expected" | "missing";

/** Why a card is not fully shown. A closed list so the copy layer (stage C) can word each one. */
export type UnifiedGapReason =
  | "no_data"                 // nothing entered yet
  | "partial_data"            // the server marked the answer partial
  | "stale_data"              // the newest figure is older than the server's threshold
  | "no_goal_selected"        // funding sources / gap need a chosen goal
  | "goal_incomplete"         // the goal has no amount or no date
  | "assumptions_required"    // pace needs assumptions the owner has not given
  | "request_failed";         // the card's own request failed

/** A figure exactly as the server sent it. `value` is passed through, never computed or summed on the client. */
export interface UnifiedFigure {
  label: string;
  value: number | null;       // null = missing (shown as "חסר"), never 0
  certainty: UnifiedCertainty;
  /** Server date the figure refers to, if it sent one (ISO yyyy-mm-dd). */
  as_of: string | null;
  /** Server codes that explain the figure (conditions, `allocated_elsewhere`, `missing_inputs`...), shown verbatim when unknown. */
  notes: readonly string[];
}

/** One card. `figures` are shown side by side; there is intentionally NO total field on a card or on the screen. */
export interface UnifiedCard<K extends UnifiedCardKey = UnifiedCardKey> {
  key: K;
  status: UnifiedCardStatus;
  /** Set when `status` is `partial`, `missing` or `unavailable`. */
  reason: UnifiedGapReason | null;
  figures: readonly UnifiedFigure[];
  /** Detail shown only after the owner opens the card (progressive disclosure). */
  expandable: boolean;
}

/** The raw server answers the model reads, one slot per card. `undefined` = not requested yet; `null` = requested and unavailable. */
export interface UnifiedScreenInputs {
  netWorth?: FccNetWorth | null;
  pace?: PaceView | null;
  overview?: FccOverview | null;
  fundingPlan?: FundingPlan | null;
}

/** The goal chosen for the funding / gap cards, by id. Without one those two cards stay closed (no request is sent). */
export interface UnifiedScreenSelection {
  goalId: string | null;
}

/** What the screen renders. Read-only: nothing here is a write request, and no field is a sum across cards. */
export interface UnifiedScreenModel {
  cards: readonly UnifiedCard[];
  selection: UnifiedScreenSelection;
}
