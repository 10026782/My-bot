// Pure presentation helpers for the compact Command Center screen.
// No React/JSX here on purpose — keeps this testable with plain node + esbuild,
// no component-rendering test framework needed for logic-only rules.

import type {
  CommandCenterAttentionItem,
  CommandCenterDevelopmentItem,
  CommandCenterDevelopmentStatus,
} from "../types";

export interface CompactDevelopmentItem extends CommandCenterDevelopmentItem {
  closed: boolean;
}

const DEVELOPMENT_GROUPS: (keyof Pick<
  CommandCenterDevelopmentStatus,
  "current_focus" | "next_actions" | "needs_verification" | "blocked" | "owner_decisions" | "recently_closed"
>)[] = ["current_focus", "next_actions", "needs_verification", "blocked", "owner_decisions", "recently_closed"];

/** Keep first occurrence only, preserving whatever order the caller passed in. */
export function dedupeDevelopmentItems<T extends { initiative_key: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.initiative_key)) return false;
    seen.add(item.initiative_key);
    return true;
  });
}

/**
 * One row per initiative, even though the backend still exposes the same
 * initiative under multiple groups (current_focus/next_actions/etc). Walks
 * the groups in the backend's own upstream order and keeps first occurrence,
 * so ordering stays deterministic without re-deriving priority in the UI.
 */
export function buildDevelopmentList(status: CommandCenterDevelopmentStatus): CompactDevelopmentItem[] {
  const merged = DEVELOPMENT_GROUPS.flatMap((group) => status[group]);
  return dedupeDevelopmentItems(merged).map((item) => ({ ...item, closed: item.work_state === "CLOSED" }));
}

const HORIZON_BUCKET: Record<string, string> = {
  H0: "עכשיו",
  H1: "קרוב",
  H2: "קרוב",
  H3: "בהמשך",
  H4: "בהמשך",
  H5: "בהמשך",
  H6: "עתידי",
  H7: "עתידי",
};

/** H0-H7 stay canonical internally; owner-facing UI only ever sees the bucket. */
export function horizonBucketLabel(horizon: string): string {
  return HORIZON_BUCKET[horizon] ?? horizon;
}

/** Healthy/current freshness is silent noise — only surface it when it isn't. */
export function shouldShowFreshness(freshness: string): boolean {
  return freshness !== "CURRENT";
}

/** A non-current projection must never be rendered as if it were live data. */
export function isCurrentFreshness(freshness: string): boolean {
  return freshness === "CURRENT";
}

const APPROVALS_HEADLINE_KEY = "approvals.pending";

/** The projection's headline card is redundant once the section has its own title. */
export function actionableApprovalEntries(
  pendingDecisions: CommandCenterAttentionItem[],
): CommandCenterAttentionItem[] {
  return pendingDecisions.filter((item) => item.signal_key !== APPROVALS_HEADLINE_KEY);
}
