// Plain node + esbuild test, no framework: run via `npm test` (see package.json).
// Mirrors the repo's existing convention of small self-contained runnable checks
// rather than a per-function test suite. Deliberately avoids `node:` imports and
// the `process` global so this file stays valid under the browser-lib tsconfig
// that `npm run build` type-checks (no @types/node in this project).
import type { CommandCenterAttentionItem, CommandCenterDevelopmentItem, CommandCenterDevelopmentStatus } from "../types";
import {
  actionableApprovalEntries,
  buildDevelopmentList,
  dedupeDevelopmentItems,
  horizonBucketLabel,
  shouldShowFreshness,
} from "./commandCenterPresentation";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) {
    if (actual !== expected) {
      throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
  },
  deepEqual(actual: unknown, expected: unknown, message?: string) {
    const a = JSON.stringify(actual);
    const b = JSON.stringify(expected);
    if (a !== b) {
      throw new Error(message ?? `expected ${b}, got ${a}`);
    }
  },
};

let failures = 0;

function test(name: string, fn: () => void) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    failures += 1;
    console.error(`FAIL - ${name}`);
    console.error(error);
  }
}

function devItem(overrides: Partial<CommandCenterDevelopmentItem>): CommandCenterDevelopmentItem {
  return {
    initiative_key: "KEY",
    title: "Program Name",
    horizon: "H0",
    work_state: "ACTIVE",
    current_stage: "stage",
    evidence_state: "PLANNED",
    next_step: "next",
    needs_verification: false,
    blocked: false,
    owner_decision_required: false,
    freshness: "CURRENT",
    last_reconciled: "2026-08-16T00:00:00Z",
    ...overrides,
  };
}

function emptyDevelopmentStatus(overrides: Partial<CommandCenterDevelopmentStatus>): CommandCenterDevelopmentStatus {
  return {
    current_focus: [],
    next_actions: [],
    needs_verification: [],
    blocked: [],
    owner_decisions: [],
    recently_closed: [],
    projection_state: "CURRENT",
    ...overrides,
  };
}

function approvalItem(overrides: Partial<CommandCenterAttentionItem>): CommandCenterAttentionItem {
  return {
    signal_key: "x",
    category: "approval",
    severity: "WARNING",
    state: "ATTENTION",
    title: "t",
    summary: "s",
    reason: "r",
    destination: "approvals",
    owner_action_required: true,
    freshness: "current",
    ...overrides,
  };
}

// --- horizon mapping (requirement #4) ---
test("horizon H0 maps to now", () => assert.equal(horizonBucketLabel("H0"), "עכשיו"));
test("horizon H1/H2 maps to soon", () => {
  assert.equal(horizonBucketLabel("H1"), "קרוב");
  assert.equal(horizonBucketLabel("H2"), "קרוב");
});
test("horizon H3-H5 maps to later", () => {
  assert.equal(horizonBucketLabel("H3"), "בהמשך");
  assert.equal(horizonBucketLabel("H4"), "בהמשך");
  assert.equal(horizonBucketLabel("H5"), "בהמשך");
});
test("horizon H6/H7 maps to future", () => {
  assert.equal(horizonBucketLabel("H6"), "עתידי");
  assert.equal(horizonBucketLabel("H7"), "עתידי");
});
test("unknown horizon falls back to raw value", () => assert.equal(horizonBucketLabel("H9"), "H9"));

// --- freshness suppression (requirement #4) ---
test("healthy CURRENT freshness is suppressed", () => assert.equal(shouldShowFreshness("CURRENT"), false));
test("STALE/PARTIAL/UNKNOWN freshness is shown", () => {
  assert.equal(shouldShowFreshness("STALE"), true);
  assert.equal(shouldShowFreshness("PARTIAL"), true);
  assert.equal(shouldShowFreshness("UNKNOWN"), true);
});

// --- dedupe (requirement #2/#3) ---
test("dedupe keeps first occurrence only", () => {
  const items = [{ initiative_key: "A" }, { initiative_key: "B" }, { initiative_key: "A" }];
  const result = dedupeDevelopmentItems(items);
  assert.deepEqual(result.map((i) => i.initiative_key), ["A", "B"]);
});

// --- one initiative, one row, across multiple backend groups (requirement #2/#3) ---
test("initiative present in multiple groups appears once, in upstream group order", () => {
  const shared = devItem({ initiative_key: "SHARED", title: "Shared Program" });
  const status = emptyDevelopmentStatus({
    current_focus: [shared],
    blocked: [shared],
    owner_decisions: [shared],
  });
  const result = buildDevelopmentList(status);
  assert.equal(result.length, 1);
  assert.equal(result[0].initiative_key, "SHARED");
  // human-readable title stays the primary field, not the initiative key
  assert.equal(result[0].title, "Shared Program");
});

test("closed flag is derived from work_state, not a separate backend field", () => {
  const closed = devItem({ initiative_key: "C1", work_state: "CLOSED" });
  const result = buildDevelopmentList(emptyDevelopmentStatus({ recently_closed: [closed] }));
  assert.equal(result[0].closed, true);
});

test("next step survives onto the compact row", () => {
  const item = devItem({ initiative_key: "N1", next_step: "Ship the thing" });
  const result = buildDevelopmentList(emptyDevelopmentStatus({ next_actions: [item] }));
  assert.equal(result[0].next_step, "Ship the thing");
});

// --- pending decisions: hide headline, keep actionable entries (requirement #7) ---
test("zero actionable approvals means an empty entry list (section hides)", () => {
  assert.deepEqual(actionableApprovalEntries([]), []);
});

test("headline summary card is stripped, individual actionable approvals remain", () => {
  const headline = approvalItem({ signal_key: "approvals.pending", title: "החלטות ממתינות" });
  const preview = approvalItem({ signal_key: "approvals.pending.preview:gmail_send_draft-lead", title: "gmail_send_draft" });
  const result = actionableApprovalEntries([headline, preview]);
  assert.equal(result.length, 1);
  assert.equal(result[0].signal_key, preview.signal_key);
});

if (failures > 0) {
  throw new Error(`${failures} test(s) failed`);
}
console.log("\nall commandCenterPresentation tests passed");
