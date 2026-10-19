export interface ProjectCard {
  id: string;
  slug: string;
  name: string;
  emoji: string;
  mode: string;
  project_type: string;
  domain: string;
  status: string;
  status_color: "red" | "yellow" | "green";
  kpi: { label: string; value: number };
  exception: string | null;
}

export interface GlobalKpis {
  overdue_tasks: number;
  hot_leads_count: number;
}

export interface ProjectsResponse {
  global_kpis: GlobalKpis;
  exceptions: string[];
  projects: ProjectCard[];
}

export interface MarketingDemandStatus {
  title: string;
  domain: string;
  stage: string;
  status: string;
  next_action: string;
  detail: string;
  pending_creative_count: number;
  consistency_state: "consistent" | "inconsistent";
}

export interface MarketingStatusResponse {
  count: number;
  demands: MarketingDemandStatus[];
}

export interface AuthResponse {
  ok: boolean;
  role: string;
  name: string;
  user_id: string;
  allowed_domains: string[];
  modes_available: string[];
}

export interface LeadSummary {
  id: string;
  name: string;
  phone: string;
  status: string;
  score: number;
  score_color: "red" | "yellow" | "blue";
  temperature: string;
  domain: string;
  source: string;
  next_step: string;
  next_step_label: string;
  experience_status?: string;
}

export interface LeadsResponse {
  view: string;
  available_views: Record<string, string>;
  available_domains: string[];
  available_sources: string[];
  next_action_options: NextActionOption[];
  status: string;
  source: string;
  next_action: string;
  temperature: string;
  experience_status?: string;
  experience_status_options?: string[];
  date_range: string;
  has_more: boolean;
  count: number;
  leads: LeadSummary[];
}

export interface TimelineEntry {
  summary: string;
  channel: string;
}

export interface Approval {
  id: string;
  action: string;
  requested_by: string;
  requested_at: string;
  risk_level: string;
  context_type: string;
  context_id: string;
  status: string;
  // Command Center approvals read-model alignment: derived server-side from
  // the canonical ActionContract (core/action_gateway.py), never from this
  // row's own status field. actionable=false must always disable/hide
  // approve-reject actions in the UI — the backend already refuses to
  // execute on these regardless, but the UI must not offer a button that
  // can only fail.
  action_contract_id: string;
  legacy_read_only: boolean;
  projected_lifecycle_status: string;
  actionable: boolean;
}

export interface ApprovalsResponse {
  count: number;
  approvals: Approval[];
}

export interface Asset {
  id: string;
  name: string;
  type: string;
  current_value: number;
  mortgage_balance: number;
  equity: number;          // Airtable formula: Current Value - Mortgage Balance
  ownership_pct: number;
  my_equity: number;       // Airtable formula: Equity * (Ownership % / 100)
  monthly_income: number;  // Gross only — no personal income calculations
  status: string;
}

export interface AssetsResponse {
  count: number;
  total_value: number;
  total_debt: number;
  total_equity: number;
  my_equity: number;
  monthly_income: number;
  assets: Asset[];
}

export interface FinancePulse {
  period: string;
  income:   { amount: number; count: number };
  pending:  { amount: number; count: number };
  overdue:  { amount: number; count: number };
  expenses: { amount: number; count: number };
  net: number;
  recent: { ref: string; amount: number; date: string; status: string }[];
}

export interface EmergencyFlagState {
  enabled: boolean;
  operation_id: string | null;
}

export interface SystemHealth {
  status: "ok" | "degraded" | "emergency";
  services: {
    airtable:  string;
    telegram:  string;
    anthropic: string;
  };
  emergency_flags:  Record<string, EmergencyFlagState>;
  active_emergency: string[];
  checked_at: string;
}

export interface ActivityEntry {
  id: string;
  title: string;
  summary: string;
  channel: string;
  domain: string;
  timestamp: string;
  sentiment: string;
}

export interface ActivityResponse {
  count: number;
  entries: ActivityEntry[];
}

export interface NextActionOption {
  value: string;
  label: string;
}

export interface LeadDetail {
  id: string;
  name: string;
  phone: string;
  domain: string;
  status: string;
  score: number;
  score_color: "red" | "yellow" | "blue";
  temperature: string;
  source: string;
  summary: string;
  next_step: string;
  next_step_label: string;
  next_step_options: NextActionOption[];
  created_at: string;
  timeline: TimelineEntry[];
  outcome?: string;
  next_followup?: string;
  owner?: string | string[];  // Airtable multipleRecordLinks returns string[]
  experience_status?: string;
  experience_status_options?: string[];
}

export interface DailyTask {
  id: string;
  task: string;
  coins: number;
  status: "Todo" | "Done" | "Skipped";
  who: string;
}

export interface GameWorld {
  id: string;
  name: string;
  number: number;
  boss: string;
  prize: string;
  coins_earned: number;
  coins_target: number;
  progress_pct: number;
}

export interface GameToday {
  today: string;
  tasks: DailyTask[];
  world: GameWorld | null;
  total_coins: number;
}

export interface CheckinTask {
  id: string;
  title: string;
  topic: string | null;
  urgency: string | null;
  source: string | null;
  required: boolean;
  xp: number;
  status: "todo" | "done";
  due_date: string | null;
  completed_at: string | null;
  carry_over_candidate: boolean;
}

export interface GameCheckin {
  date: string;
  tasks: CheckinTask[];
  total_xp: number;
  updated_at: string;
  updated_by: string;
  world: GameWorld | null;
}

export interface DashboardResponse {
  project_slug: string;
  domain: string;
  name: string;
  leads_count: number;
  open_deals: number;
  open_tasks: number;
  leads: LeadSummary[];
}

export interface OwnerControlCenter {
  ok: boolean;
  system_health: {
    health_percent: number;
    working_count: number;
    partial_count: number;
    broken_count: number;
  };
  critical_systems: {
    name: string;
    status: string;
    color: "green" | "yellow" | "red" | string;
    owner?: string;
    next_blocker?: string;
  }[];
  approvals: {
    pending_count: number;
    pending: Approval[];
    recent_executed: Approval[];
    recent_receipts: {
      id: string;
      title: string;
      timestamp: string;
      receipt: {
        action?: string;
        table?: string;
        record_id?: string;
        requested_by?: string;
        approved_by?: string;
        status?: string;
        timestamp?: string;
      };
    }[];
  };
  permissions: {
    role: string;
    read: string;
    write: string;
    approve: string;
  }[];
  business_language: {
    lead_status: { value: string; label: string }[];
    lead_outcome: { value: string; label: string }[];
    lead_tier: { value: string; label: string }[];
  };
  strategic_pipeline?: {
    stage_counts: Record<string, number>;
    total: number;
    active: number;
  };
  blockers: string[];
  next_actions: string[];
  warnings: string[];
}

export interface CommandCenterAttentionItem {
  signal_key: string;
  category: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  state: "OK" | "ATTENTION" | "UNKNOWN" | "STALE";
  title: string;
  summary: string;
  reason: string;
  destination: string;
  owner_action_required: boolean;
  freshness: string;
}

export interface CommandCenterSourceStatus {
  source: string;
  state: "CURRENT" | "STALE" | "UNKNOWN" | "UNSUPPORTED";
  freshness: string;
  reason?: string | null;
}

export interface CommandCenterDevelopmentItem {
  initiative_key: string;
  title: string;
  horizon: string;
  work_state: string;
  current_stage: string;
  evidence_state: string;
  next_step: string;
  needs_verification: boolean;
  blocked: boolean;
  owner_decision_required: boolean;
  freshness: "CURRENT" | "STALE" | "UNKNOWN";
  last_reconciled: string;
}

export interface CommandCenterDevelopmentStatus {
  current_focus: CommandCenterDevelopmentItem[];
  next_actions: CommandCenterDevelopmentItem[];
  needs_verification: CommandCenterDevelopmentItem[];
  blocked: CommandCenterDevelopmentItem[];
  owner_decisions: CommandCenterDevelopmentItem[];
  recently_closed: CommandCenterDevelopmentItem[];
  projection_state: "CURRENT" | "PARTIAL" | "UNKNOWN";
}

export interface CommandCenterSectionStatus {
  state: "CURRENT" | "STALE" | "PARTIAL" | "UNKNOWN";
  reason: string;
  source_version: string;
}

export interface CommandCenterSystemStatus {
  state: "CURRENT" | "ATTENTION" | "STALE" | "PARTIAL" | "UNKNOWN";
  freshness: string;
  reason?: string | null;
}

export interface CommandCenterResponse {
  attention: {
    items: CommandCenterAttentionItem[];
    pending_decisions: CommandCenterAttentionItem[];
    source_status: CommandCenterSourceStatus[];
    overall_state: "OK" | "ATTENTION" | "UNKNOWN" | "STALE";
  };
  pending_decisions: CommandCenterAttentionItem[];
  business_status: CommandCenterSectionStatus;
  system_status: CommandCenterSystemStatus;
  development_status: CommandCenterDevelopmentStatus;
  recent_activity: CommandCenterSectionStatus;
  freshness: Record<string, "CURRENT" | "STALE" | "PARTIAL" | "UNKNOWN">;
  generated_at: string;
  overall_state: "OK" | "ATTENTION" | "PARTIAL" | "UNKNOWN";
}

export interface TaskWorkItem {
  stable_key: string;
  title: string;
  description: string;
  status: string;
  due_date: string | null;
  owner: string;
  domain: string;
  source_type: string;
  source_ref: string;
  overdue: boolean;
  destination: string;
  actionable: boolean;
}

export interface MyWorkResponse {
  ok: boolean;
  immediate: TaskWorkItem[];
  upcoming: TaskWorkItem[];
  generated_at: string;
}

export type VentureStage =
  | "Research"
  | "Supplier/Source Contact"
  | "Due Diligence"
  | "Legal/Tax Review"
  | "Smoke Test"
  | "GO"
  | "NO-GO"
  | "Converted";

export interface Venture {
  id: string;
  name: string;
  stage: string;
  domain: string;
  conviction: string;
  estimated_potential: number;
  target_decision_date: string;
  decision_log: string;
  next_action: string;
  notes: string;
  linked_contacts: string[];
  owner: string[];
  converted_to_deal: string[];
  created_at: string;
}

export interface VenturesResponse {
  count: number;
  ventures: Venture[];
}

// Leads.status (airtable_schema.py::LeadStatus) — single Hebrew label map shared
// by the pipeline filter, the lead card and the lead detail. A value missing
// here still renders (falls back to the raw key) rather than disappearing.
export const LEAD_STATUS_LABELS: Record<string, string> = {
  new: "חדש — טרם דיברנו",
  waiting_call: "ממתין לשיחה",
  active: "בטיפול",
  waiting_response: "במעקב",
  high_confidence: "מתאים — רציני",
  needs_convincing: "דיברנו — צריך שכנוע",
  done: "הושלם",
  archived: "בארכיון",
  lost: "אבוד",
  duplicate: "כפילות",
  not_relevant: "לא רלוונטי",
};

// Non-terminal statuses an employee can move a lead between ("where the lead is").
export const LEAD_OPEN_STATUSES = ["new", "waiting_call", "active", "waiting_response", "needs_convincing", "high_confidence"] as const;

export function leadStatusLabel(status: string): string {
  return LEAD_STATUS_LABELS[(status ?? "").trim()] ?? status;
}

// ── Private Financial Control Center (owner-of-record only) ──────────────
export interface FccGoalRow {
  goal_id: string;
  title: string | null;
  category: string | null;
  priority: number | null;
  /** Standing-order savings only: actual deposits vs the standing level (plan). */
  deposited_month?: number;
  gap_month?: number;
  gap_last_month?: number;
  method: string;
  /** Goal family: recurring (period sum) | monthly_level (run-rate change) | cumulative | project (no amount). */
  mode: "recurring" | "monthly_level" | "cumulative" | "project";
  end_date: string | null;
  /** The End Date is an estimate, uncertain by ± this many whole months (0 = firm). */
  date_margin_months?: number;
  period_start: string;
  period_end: string;
  target: number | null;
  actual: number | null;
  /** Direct costs of earning this income (fuel, parking, fees) and net = gross `actual` - costs. */
  direct_costs?: number | null;
  net?: number | null;
  remaining: number | null;
  remaining_periods: number | null;
  dynamic_target_per_week: number | null;
  weekly?: FccWeekly | null;
  status: "in_progress" | "achieved" | "overdue" | "missing_target" | "project";
  next_action?: { title: string | null; due_date: string | null } | null;
  period_type?: string;
  /** Explicit "Contributes To" link: this goal is a source inside its parent, never added on top of it. */
  parent_id?: string | null;
  is_source?: boolean;
  sources?: FccSource[];
  weekly_sources_required?: number;
  other_sources_needed?: number | null;
}

/** The fixed weekly quota of a monthly goal (target / days-in-month × 7, per-day month rates) with the carry from earlier weeks. */
export interface FccWeekly {
  week_start: string;
  week_end: string;
  quota: number;
  /** Shortfall carried from earlier weeks (negative = a surplus that lowers this week's need). */
  carry_in: number;
  required: number;
  actual: number;
  remaining: number;
  surplus: number;
  /** actual - (quota + carry_in): > 0 a surplus to relax with or set aside, < 0 a shortfall that moves on. */
  balance: number;
  history?: { week_start: string; week_end: string; quota: number; actual: number; balance: number }[];
  /** The open question "what to do with the week's surplus?" (null = nothing to ask). The server finds the week and the amount. */
  closing?: { kind: "week" | "month"; month?: string; week_start: string; week_end: string; amount: number; goal_id?: string } | null;
  /** Surplus kept for the month-end decision, all weeks of the month so far (the mid-month picture). */
  held_total?: number;
}

export interface FccRecentIncome {
  id: string | null;
  date: string;
  goal_id: string;
  source: string | null;
  kind: "one_time" | "direct_cost";
  amount: number;
  note: string | null;
  possible_duplicate: boolean;
}

export interface FccSource {
  goal_id: string;
  title: string | null;
  period_type: string | null;
  target: number;
  actual: number;
  remaining: number | null;
  direct_costs?: number | null;
  net?: number | null;
}

export interface FccSummaryCard {
  mode?: string;
  deposited_month?: number;
  gap_month?: number;
  gap_last_month?: number;
  target: number;
  actual: number;
  remaining: number;
  direct_costs?: number;
  net?: number;
  dynamic_target_per_week: number;
  weekly?: FccWeekly;
  goals: number;
  sources?: FccSource[];
  weekly_sources_required?: number;
  other_sources_needed?: number;
}

export interface FccLoan {
  id: string;
  name: string | null;
  lender: string | null;
  loan_type: "פרטית" | "עסקית" | "משכנתא" | null;
  related_asset: string | null;
  related_asset_name: string | null;
  original_amount: number | null;
  early_closure_balance: number | null;
  interest_rate: number | null;
  monthly_payment: number | null;
  payments_remaining: number | null;
  end_date: string | null;
  early_repayment_fee: string | null;
  active: boolean;
  /** owed_by_me (default) | owed_to_me: a debt owed TO the owner — listed apart, never part of his liabilities. */
  direction?: "owed_by_me" | "owed_to_me";
  /** How the debt is repaid: a standing monthly amount, a deadline, or null (nothing recorded yet). */
  arrangement?: "monthly" | "deadline" | null;
  /** Next instalment date (the monthly auto-step moves it on) and "every instalment paid" (the owner confirms the closing). */
  next_payment_due?: string | null;
  payments_done?: boolean;
  /** The OPEN next actions of this loan / debt (Tasks tagged with the loan). */
  actions?: FccAssetAction[];
  /** Active Loan unchecked and not Paid Off: shown and counted, flagged for confirmation. */
  status_unknown: boolean;
  months_remaining: number | null;
  estimated_total_remaining_payments: number | null;
  estimated_future_cost: number | null;
  future_cost_exact: boolean;
  monthly_cash_freed_if_closed: number | null;
  annual_interest_cost: number | null;
  missing: string[];
}

export interface FccLoanBucket { count: number; early_closure_balance: number | null; monthly_payments: number | null }

export interface FccPayoffRow {
  id: string;
  name: string | null;
  lender: string | null;
  loan_type: string | null;
  amount_to_close: number | null;
  interest_rate: number | null;
  monthly_cash_freed: number | null;
  months_remaining: number | null;
  estimated_remaining_payments: number | null;
  /** Continuation cost estimate = monthly × remaining payments − closure (null when data is inconsistent/suspicious). */
  estimated_future_cost: number | null;
  future_cost_exact: boolean;
  /** What closing now could avoid: continuation cost − known early-repayment fee (null = unknown / excluded). */
  cost_saving: number | null;
  cost_saving_exact: boolean;
  no_saving: boolean;
  data_inconsistent: boolean;
  data_suspicious: boolean;
  data_issue: "inconsistent" | "suspicious" | null;
  annual_interest_burden: number | null;
  scores: Record<"interest" | "cash" | "closure" | "time", number | null>;
  balanced_score: number | null;
  score_coverage: number;
  score_coverage_label: string;
  missing_factors: ("interest" | "cash" | "closure" | "time")[];
  partial: boolean;
}

export type PayoffStrategy = "balanced" | "interest" | "cash" | "savings";

export interface FccPayoff {
  weights: Record<"interest" | "cash" | "closure" | "time", number>;
  items: FccPayoffRow[];
  rankings: Record<PayoffStrategy, string[]>;
}

export interface FccScenarioResult {
  budget: number;
  used: number;
  remaining_budget: number;
  closed_count: number;
  closed: { id: string; name: string | null; amount_to_close: number; monthly_cash_freed: number | null; cost_saving: number | null; cost_saving_exact: boolean }[];
  debt_removed: number;
  monthly_cash_released: number | null;
  future_cost_saved: number | null;
  future_cost_saved_exact: boolean;
  partial: boolean;
  skipped_over_budget: string[];
  excluded_unknown_amount: string[];
  excluded_no_data: string[];
}

export interface FccScenarios {
  budget: number;
  strategies: Record<PayoffStrategy, FccScenarioResult>;
  optimal: { cash: FccScenarioResult | null; saved: FccScenarioResult | null };
}

export interface FccLoans {
  items: FccLoan[];
  summary: {
    total_active_loans: number;
    total_original_amount: number | null;
    total_early_closure_balance: number | null;
    total_monthly_payments: number | null;
    weighted_average_interest_rate: number | null;
    total_estimated_future_cost: number | null;
    total_monthly_cash_freed_if_all_closed: number | null;
    coverage: { original_amount: number; early_closure_balance: number; monthly_payment: number; future_cost: number; interest_rate: number };
    incomplete_count: number;
    unknown_status_count: number;
    future_cost_exact: boolean;
    by_type: Record<string, FccLoanBucket>;
    by_asset: (FccLoanBucket & { asset_id: string; asset_name: string | null })[];
  };
  rankings: { high_interest: string[]; cash_freed: string[]; small_balance: string[] };
  goal: { target: number; closed: number | null; remaining: number | null; active_closure_balance: number | null } | null;
  payoff?: FccPayoff;
  /** Debts owed TO the owner (apart from the liabilities above). */
  receivables?: { count: number; total_balance: number | null; coverage: number; no_arrangement: number };
  /** Owed TO the owner vs owed BY him (asset-linked loans left out: that debt is already inside the asset's equity). */
  balance?: FccDebtBalance;
  /** True when the monthly job is on: balances follow their schedule on each due date (an estimate to correct now and then). */
  auto_step?: boolean;
}

export interface FccDebtBalance {
  receivables_total: number; liabilities_total: number; net: number | null;
  financial_asset: number | null;      // max(net, 0): a negative net is NOT an asset
  net_debt: number | null;             // min(net, 0)
  linked_excluded_count: number; linked_excluded_total: number;
  missing_receivables: number; missing_liabilities: number; receivables_count: number;
}

/** Personal equity = the owner's share of his active assets + the net debt position. */
export interface FccPersonalEquity {
  assets_my_equity: number | null; assets_known: number; assets_count: number;
  financial_asset: number | null; net_debt: number | null; net: number | null; total: number | null; partial: boolean;
}

/** One OPEN next action of an asset (a Task): several may be open; ממתין -> בביצוע -> בוצע / בוטלה. */
export interface FccAssetAction { id: string; title: string | null; status: string; due_date: string | null; owner: string | null; history: string }

export interface FccAssetItem {
  id: string;
  name: string | null;
  asset_type: string | null;
  status: string | null;
  current_value: number | null;
  monthly_income: number | null;
  mortgage_balance: number | null;
  ownership_pct: number | null;
  next_step: string | null;
  next_step_owner: string | null;
  actions?: FccAssetAction[];       // open next actions (Tasks); next_step above is the LEGACY single text, left as stored
  equity: number | null;
  my_equity: number | null;
  linked_loans: { id: string; name: string | null; loan_type: string | null; early_closure_balance: number | null; monthly_payment: number | null; interest_rate: number | null }[];
  linked_debt: number | null;
  linked_debt_known: number;
  linked_monthly_payments: number | null;
}

/** A sold asset, listed apart from the active ones (never part of the active totals). */
export interface FccSoldAsset {
  id: string;
  name: string | null;
  sale_date: string | null;
  sale_amount: number | null;       // FULL (100%) sale price
  ownership_pct: number | null;
  my_share: number | null;          // price × Ownership %; null when either is unknown (100% is never assumed)
  linked_loans: { id: string; name: string | null; early_closure_balance: number | null }[];   // stay OPEN after a sale
}

export interface FccAssets {
  items: FccAssetItem[];
  sold?: { count: number; items: FccSoldAsset[] };
  summary: {
    count: number;
    total_value: number | null; total_mortgage: number | null; total_equity: number | null; total_my_equity: number | null; total_monthly_income: number | null;
    coverage: { value: number; mortgage: number; equity: number; my_equity: number; monthly_income: number };
    linked_loans_count: number; linked_loans_debt: number | null;
    unlinked_loans_count: number; unlinked_loans_debt: number | null;
    personal_equity?: FccPersonalEquity;
  };
}

/** What the month frees for savings (server-derived): the fixed income is "free" once the income goal is met from the other sources. */
export interface FccSavingsRelease {
  income_net: number; income_target: number; fixed_level: number; shortfall: number; from_fixed: number; extra: number;
  available: number; deposited: number; remaining: number; expected: number; gap: number;
  month: string; closing: boolean; destination: { id: string; title: string | null } | null;
}

/** Self-reported deposit history (server-derived from existing events; nothing stored, nothing verified against a bank or fund). */
export interface FccSavingsHistory {
  ytd: number; ytd_plan: number; ytd_gap: number; months_elapsed: number; monthly_average: number; streak: number;
  last_deposit: string | null; deposit_count: number; recent: { month: string; deposited: number; plan: number }[];
}

/** One financial account as the server derives it (D1 step 5/7). The value is the latest dated balance snapshot (a FACT); the
 *  `estimate` is a separate, labelled projection from movements after it. No free-text notes ever arrive here. */
export interface FccAccount {
  id: string; name: string | null; account_type: string | null; institution: string | null; holder_names: string | null;
  status: string | null; liquidity: string | null; liquid_from: string | null; tax_treatment: string | null; management_fee_pct: number | null;
  /** Owner-entered forecast inputs (D1 step 9); null = not known, never invented. */
  planned_monthly_deposit: number | null; deposit_fee_pct: number | null; investment_track: string | null; linkage: string | null;
  linkage_notes: string | null; expected_return_pct: number | null; insurance_cost_monthly: number | null; insurance_cost_as_of: string | null;
  balance: { value: number; as_of: string; verification: string; estimate: { value: number; movements_since: number; movement_count: number; label: "estimate" } } | null;
}
export interface FccAccountsView {
  accounts: FccAccount[];
  totals: { consolidated_value: number | null; estimated_value: number | null; accounts_with_value: number; accounts_without_snapshot: number;
            closed_accounts: number; oldest_snapshot: string | null; all_self_reported: boolean | null };
  skipped_events: number;
  as_of: string;
}

/** Assumption-based forecast per account + consolidated (D1 step 7 / A1). Server-derived by the unchanged portfolio_lab engine. */
export interface FccForecastParams {
  years: number; annual_return_pct: number; annual_fee_pct: number; inflation_pct: number; monthly_contributions: Record<string, number>;
}
export type FccLiquidityState = "accessible" | "conditional" | "locked";
export interface FccForecastPoint { year: number; nominal: number; real: number; invested: number; accessible?: number; conditional?: number; locked?: number }
/** Potential coverage of one goal at its due month (accessible only); the same money may appear in several goals until B2. */
export interface FccGoalCoverage {
  id: string | null; title: string | null; category: string; target_amount: number | null; due_month: string | null;
  verdict: "covered" | "short" | "not_comparable";
  reason: "missing_target" | "missing_date" | "past_date" | "beyond_horizon" | "no_verified_accessible_account" | "over_allocated" | "allocated_not_accessible"
        | "allocation_not_yet_effective" | "allocation_effective_after_due" | null;
  gap: number | null; accessible_value: number | null; conditional_value: number | null; locked_value: number | null;
  /** B2: "allocation" = counted from the owner's allocation rows only; "potential" = A2 coverage of all accessible money. All numbers are the server's. */
  basis?: "allocation" | "potential"; planned_allocated_value?: number | null; allocated_value?: number | null; allocation_gap?: number | null;
  allocation_capped?: boolean; allocated_elsewhere_accessible?: number; unallocated_accessible_value?: number | null; potential_caveat?: "allocated_elsewhere" | null;
}
/** B2 allocation overview (server-computed, read-only). An allocation is a label on money, never a movement and never liquidity. */
export interface FccAllocationAccount {
  id: string; name: string | null; value: number; as_of: string | null; liquidity_state: FccLiquidityState; allocated: number; allocated_pct: number | null;
  unallocated: number; over_allocated: boolean; over_by: number;
  allocations: { id: string; goal_id: string; goal_title: string | null; mode: "percent" | "fixed_amount"; percent: number | null; amount: number | null; resolved_amount: number; counted: boolean }[];
}
export interface FccAllocationGoal {
  id: string; title: string | null; allocated: number; accessible: number; conditional: number; locked: number;
  blocked_by_over_allocation: number; status: "ok" | "partial_over_allocation" | "blocked_over_allocation";
}
export interface FccAllocations {
  as_of: string; has_allocations: boolean; count: number;
  totals: { accounts_value: number; allocated: number; unallocated: number; over_allocated: number };
  accounts: FccAllocationAccount[]; goals: FccAllocationGoal[]; skipped: Record<string, number>;
  over_allocated_accounts: number; duplicate_goal_account_pairs: number;
}
export interface FccForecastAccount {
  id: string; name: string | null; account_type: string | null; start_value: number; start_as_of: string; verification: string | null;
  monthly_contribution: number; monthly_contribution_source: "typed" | "account" | "default"; fee_pct: number; fee_source: "account" | "default";
  deposit_fee_pct: number; deposit_fee_known: boolean; return_pct: number; return_source: "account" | "default";
  return_kind: "nominal" | "real_to_nominal"; linkage: string | null; investment_track: string | null;
  insurance_cost_monthly: number; insurance_cost_known: boolean; insurance_cost_as_of: string | null;
  deposit_fees_paid: number; insurance_paid: number; missing: string[];
  /** A2: classification only, never an entitlement to withdraw. */
  liquidity?: { basis: "immediate" | "retirement_immediate" | "dated" | "undated" | "unverified"; liquid_from: string | null;
                state_now: FccLiquidityState; state_at_horizon: FccLiquidityState };
  final_nominal: number; final_real: number; invested: number; nominal_profit: number; costs_paid: number; series: FccForecastPoint[];
}
export interface FccAccountsForecast {
  schema_version: string; engine_version: string; result_type: string; start_date: string; years: number;
  assumptions: { annual_return_pct: number; annual_fee_pct_default: number; inflation_pct: number; deposit_timing: string };
  accounts: FccForecastAccount[];
  consolidated: { accounts: number; start_value: number; final_nominal: number | null; final_real: number | null; invested: number | null; series: FccForecastPoint[] };
  excluded: { without_snapshot: number; closed: number };
  data_gaps?: { id: string; name: string | null; missing: string[] }[];
  goals?: FccGoalCoverage[]; goals_skipped?: { other_category: number; inactive: number };
  allocations?: FccAllocations;
  all_self_reported: boolean | null; warnings: string[]; as_of: string;
}

export interface FccOverview {
  goals: FccGoalRow[];
  savings_history?: FccSavingsHistory | null;
  savings_release?: FccSavingsRelease | null;
  loans?: FccLoans;
  assets?: FccAssets;
  summary: Partial<Record<"income" | "savings" | "emergency_fund" | "debt_repaid" | "payment_reduction", FccSummaryCard>>;
  tasks: { id: string; title: string | null; due_date: string | null; status: string | null }[];
  monthly_cash_improvement: number;
  household?: { month_total: number };
  receipts?: { missing_count: number; missing_amount: number };
  obligations?: { total_monthly: number; flagged_count: number; flagged_monthly: number; cancel_pending?: number; potential_saving: number; count: number };
  /** Latest income entries (own only), newest first, so nothing is booked twice. */
  recent_incomes?: FccRecentIncome[];
  recent_events: { goal_ids: string[]; Amount: number | null; Kind: string | null; "Occurred At": string | null; Note: string | null }[];
  as_of: string;
  draft: FccTurn | null;
}

/** One turn of the server-side FCC conversation (draft/completion). The client only renders it. */
export interface FccTurn {
  state: "ask" | "unrelated" | "review" | "confirmed" | "executed" | "cancelled" | "needs_goal" | "duplicate" | "clarify" | "denied" | "info" | "partial_failure";
  message: string;
  entity?: string | null;
  awaiting?: string | null;
  fields?: Record<string, string>;
  candidates?: { goal_id: string; title: string | null }[];
  follow_up?: "savings" | null;     // executed income: the screen offers to put the freed amount away
  follow_up_asset?: string | null;  // executed finish / cancel of a next action: the asset to ask "what is the next action?" for
}


// ── Portfolio Lab ("מעבדת העתיד"): the server's view of build_simulator_view (schema 1.0). The client only renders it. ──
export interface PlSeriesRow { year: number; nominal: number; real: number; contributions: number }
export interface PlKpis {
  final_nominal: number; final_real: number; contributions: number; nominal_profit: number; real_profit: number;
  management_fees_paid: number; total_cost_impact: number | null; net_effective_annual_return: number; real_effective_annual_return: number;
  after_tax: { value: number | null; display: string | null; note: string };
}
export interface PlCrisisStrategy {
  strategy: string; label: string; is_baseline: boolean; final_nominal: number; final_real: number;
  final_nominal_no_crisis: number; delta_vs_no_crisis: number; gap_vs_baseline: number;
}
export interface PlIntraYear {
  month: number; year: number; recovery_months: number; recovery_truncated_by_horizon: boolean;
  monthly_path: { month_index: number; t_years: number; year: number; month: number; nominal_no_crisis: number; nominal_crisis: number;
                  real_no_crisis: number; real_crisis: number; contributions: number }[];
  timing_by_month: { month: number; is_selected: boolean; final_nominal: number; final_real: number; delta_vs_no_crisis: number }[];
  deposit_order_note: string; note: string;
}
export interface PlCrisis {
  applied: boolean; intra_year?: PlIntraYear; delta_vs_no_crisis?: number; final_nominal?: number; series?: PlSeriesRow[]; by_strategy?: PlCrisisStrategy[];
  recovery_truncated_by_horizon?: boolean; note?: string;
}
export interface PlCompareSide { label: string; assumptions: Record<string, number | string | boolean>; kpis: PlKpis; series: PlSeriesRow[] }
export interface PlScenarioComparison {
  applied: boolean; strategy?: { id: string; label: string };
  changed_fields?: { field: string; label: string; a: number | string | boolean; b: number | string | boolean }[];
  a?: PlCompareSide; b?: PlCompareSide;
  gaps_b_minus_a?: Record<string, number> & { series: { year: number; nominal: number; real: number }[] };
  note?: string;
}
export interface PlBreakdown {
  contributions: number; profit_net: number; costs: number; total_before_costs: number;
  shares: { contributions: number; profit_net: number; costs: number };
}
export interface PortfolioLabView {
  schema_version: string; source: "portfolio_lab"; engine_version: string; result_type: string; currency: "ILS";
  primary_strategy: { id: string; label: string };
  kpis: PlKpis;
  charts: {
    growth: { series: PlSeriesRow[]; crisis: PlCrisis };
    strategy_comparison: Record<string, PlSeriesRow[]>;
    breakdown: PlBreakdown;
    scenario_comparison?: PlScenarioComparison;
    sensitivity: {
      monthly_contribution: { factor: number; monthly_contribution: number; final_nominal: number; final_real: number }[];
      duration: { years: number; final_nominal: number; final_real: number; contributions: number }[];
    };
  };
  comparison_table: { strategy: string; label: string; is_baseline: boolean; final_nominal: number; final_real: number;
                      contributions: number; net_profit: number; costs: number; gap_vs_baseline: number }[];
  insights: { topic: string; text: string }[];
  assumptions: { id: string; text: string; assumption_based: boolean }[];
  warnings: string[];
  labels: { strategies: Record<string, string>; components: Record<string, string> };
  replay_digest: string;
}
export interface PortfolioLabParams {
  initial: number; monthly_contribution: number; years: number; annual_return_pct: number; annual_fee_pct: number; inflation_pct: number;
  deposit_timing: "begin" | "end"; index_contributions: boolean; baseline: string; strategies: string[];
  crisis?: { decline_pct: number; year: number; recovery: "fast" | "prolonged"; month?: number };
  compare_to?: Partial<Pick<PortfolioLabParams, "initial" | "monthly_contribution" | "annual_return_pct" | "annual_fee_pct" | "inflation_pct">>;
}

/** Goal Funding Planner (step 1b): a neutral comparison of ways to fund one goal. Every number is the server's; nothing here is a recommendation. */
export type FundingOptionType = "existing_balance" | "new_deposits" | "asset_sale" | "loan" | "work_income" | "receivable_collection" | "obligations_reduction" | "custom";
export type FundingCertainty = "confirmed" | "expected" | "uncertain" | "unknown";
export interface FundingOptionResult {
  id: string; type: FundingOptionType; feasible: boolean | "unknown"; reason: string | null; covers_amount: number | null; available_by: string | null;
  monthly_cash_effect: number | null; one_time_cost: number | null; total_cost: number | null;
  new_liabilities: { amount: number; monthly_payment: number; term_months: number } | null;
  time_to_realize_months: number | null; certainty: FundingCertainty; conditions: string[]; risks: string[]; assumptions: string[]; missing_inputs: string[];
  provenance: Record<string, string | null>; details: Record<string, unknown>;
}
export interface FundingNeed {
  goal_id: string; title: string | null; category: string | null; target: number | null; due: string | null; months_to_due: number | null; reason: string | null;
  sizing_basis: string; date_margin_months?: number; confirmed_existing: number; expected_existing: number; progress_events_actual: number | null; gap: number | null; gap_after_expected?: number;
}
export interface FundingPlanBlock {
  allocations: { option_id: string; amount: number; certainty: FundingCertainty; available_by: string | null; conditions: string[] }[];
  covered: Record<FundingCertainty, number>; earliest_available_by: string | null;
  remaining_after_confirmed: number; remaining_after_confirmed_and_expected: number; monthly_burden: number; monthly_release: number; note: string;
}
/** One end of the date window: the same options recomputed at the earliest / latest date (server numbers). */
export interface FundingWindowOption {
  id: string; type: FundingOptionType; feasible: boolean | "unknown"; reason: string | null; covers_amount: number | null; available_by: string | null;
  monthly_cash_effect: number | null; certainty: FundingCertainty; time_to_realize_months: number | null; required_monthly: number | null;
}
export interface FundingWindowEnd { due: string | null; reason: string | null; gap: number | null; months_to_due: number | null; options: FundingWindowOption[] }
export interface FundingWindow { margin_months: number; early: FundingWindowEnd; late: FundingWindowEnd; note: string }
export interface FundingGoalResult { need: FundingNeed; options: FundingOptionResult[]; plan: FundingPlanBlock | null; window?: FundingWindow | null }
/** Funding sources step 2: candidate sources for one goal, in five SEPARATE categories (server numbers; no totals, no ranking). Missing = null. */
export type FundingSourceCategory = "liquid_now" | "liquid_by_due_date" | "conditional_on_action" | "expected_not_guaranteed" | "future_deposits";
export type FundingLiquidityState = "accessible" | "conditional" | "locked";
export interface FundingSourceItem {
  source_type: "account" | "asset" | "receivable" | "planned_deposit"; source_id: string; name: string | null;
  amount: number | null; amount_status: string; as_of: string | null; certainty: FundingCertainty;
  conditions: string[]; risks: string[]; missing_inputs: string[]; balance_effect: string | null;
  liquidity?: { basis: string; liquid_from: string | null; state_at: Record<"now" | "due" | "early" | "late", FundingLiquidityState | null> };
  allocation?: { allocated_to_this_goal: number | null; allocated_elsewhere_amount: number | null; allocated_elsewhere: boolean; over_allocated: boolean; amount_not_allocated_elsewhere: number | null };
  expected_at_due?: { label: string; guaranteed: false; amount: number | null; early: number | null; late: number | null; includes_planned_deposits: boolean; monthly_planned_deposit_included: number | null; basis?: string; note: string } | null;
  asset?: { asset_type: string | null; recorded_value: number | null; ownership_pct: number | null; mortgage_balance: number | null; linked_debt: number | null; linked_loan_names: (string | null)[]; monthly_income: number | null };
  receivable?: { arrangement: string | null; next_payment_due: string | null; end_date: string | null };
  deposit?: { monthly_planned: number; months_until_due: number | null; deposit_fee_pct: number | null; state_at: Record<"now" | "due" | "early" | "late", FundingLiquidityState | null> };
  window?: Record<"early" | "late", { months: number | null; amount: number | null }>;
  forecast_inclusion?: "included_in_forecast" | "not_included"; forecast_inclusion_note?: string;
  option_template: { type: "asset_sale" | "receivable_collection" | "new_deposits"; asset_id?: string; loan_id?: string; account_id?: string } | null; owner_must_enter: string[];
}
export interface FundingSourcesGoal {
  goal_id: string; title: string | null; target_amount: number | null; due: string | null; reason: string | null;
  date_window: { margin_months: number; early: string | null; late: string | null; note: string } | null;
  categories: Record<FundingSourceCategory, FundingSourceItem[]>; counts: Record<FundingSourceCategory, number>;
  not_available_by_due_date: FundingSourceItem[]; gaps: { future_deposits: { account_id: string; name: string | null; missing: string[] }[] };
}
export interface FundingSources {
  schema_version: string; result_type: string; as_of: string; goals: FundingSourcesGoal[];
  assumptions: { annual_return_pct: number; annual_fee_pct: number; inflation_pct: number; note: string };
  category_labels: Record<FundingSourceCategory, string>; warnings: string[];
}
/** Funding sources step 3: "what changed since the saved plan" — the saved snapshot beside the same request recomputed today (server values; comparison only). */
export type SavedPlanValue = string | number | boolean | null;
export interface SavedPlanPair { field: string; saved: SavedPlanValue; today: SavedPlanValue; changed: boolean }
export interface SavedPlanOptionChange { id: string; type: FundingOptionType | null; present_today: boolean; fields: SavedPlanPair[]; changed: boolean }
export interface SavedPlanGoalComparison {
  goal_id: string; status: "ok" | "no_saved_plan" | "unavailable"; reason?: string; plan_id?: string;
  saved?: { as_of: string | null; saved_at: string | null; plans_found: number }; today_reason?: string | null;
  need?: SavedPlanPair[]; options?: SavedPlanOptionChange[]; any_change?: boolean;
}
export interface SavedPlanComparison { schema_version: string; result_type: string; as_of: string; goals: SavedPlanGoalComparison[]; note: string }
export interface FundingPlan {
  suggested_sources?: FundingSources;
  saved_plan_comparison?: SavedPlanComparison;
  schema_version: string; result_type: string; as_of: string;
  assumptions: { annual_return_pct: number; annual_fee_pct: number; inflation_pct: number; horizon_years: number };
  goals: FundingGoalResult[];
  portfolio: { monthly_burden_in_plan: number | null; planned_monthly_savings: number | null; shortfall: number | null; capacity_known: boolean; plan_chosen: boolean; over_committed: string[] };
  warnings: string[];
}
export interface FundingRequestBody {
  goal_id: string; assumptions: { annual_return_pct: number; annual_fee_pct: number; inflation_pct: number };
  options: Record<string, unknown>[]; allocation_plan: { goal_id: string; option_id: string; amount: number }[];
  /** The goal's date is an estimate, uncertain by ± this many whole months (0 = firm). Omitted = the goal's own saved margin. */
  date_margin_months?: number;
}

/** Unified net worth (C2, server-computed, read-only): accounts + assets − own debts. Receivables are shown apart and are NOT in `net`. */
export interface FccNetWorthAsset {
  id: string; name: string | null; asset_type: string | null; as_of: string | null; gross_value: number | null; ownership_pct: number | null;
  value: number | null; debt_source: "linked_loans" | "asset_mortgage" | null; debt: number | null; debt_responsibility_known: boolean; unknown_debt_loans: number;
  ignored_mortgage_balance: number | null; counted: boolean; missing: ("missing_value" | "missing_ownership")[];
}
export interface FccNetWorth {
  as_of: string;
  net: number | null;
  partial: boolean;
  gaps: { accounts_without_balance: number; assets_left_out: number; debts_without_balance: number; asset_debts_unverified: number };
  accounts: { total: number | null; items: { id: string; name: string | null; value: number; as_of: string; verification: string; age_days: number | null; freshness: "current" | "stale" }[];
              missing: { id: string; name: string | null }[]; oldest_as_of: string | null; stale_after_days: number;
              freshness: { current: number; stale: number; missing: number } };
  assets: { total: number | null; items: FccNetWorthAsset[]; sold_excluded: number; oldest_as_of: string | null; as_of_known: boolean };
  liabilities: { total: number | null; on_assets: number | null; standalone: number | null;
                 standalone_items: { id: string; name: string | null; loan_type: string | null; balance: number | null; as_of: string | null; note: string | null }[];
                 oldest_as_of: string | null; as_of_known: boolean };
  receivables: { in_net: false; label: "expected_uncertain"; count: number; total: number | null; coverage: number; items: { id: string; name: string | null; balance: number | null }[] };
}


/** C4 — actual accumulation pace vs the plan (POST /api/fcc/pace). Every number is the server's; self_reported data; null = missing (never 0). */
export interface PaceReturnBlock {
  exact: null; days: number; documented_flow_count: number; undocumented_flows_possible: boolean;
  status: "approximate_range" | "period_too_short" | "start_balance_not_positive" | "undefined_denominator" | "not_computed_consolidated";
  range: { low: number; high: number } | null; annualized_range: { low: number; high: number } | null;
}
export interface PaceAccountRow {
  id: string; name: string | null; status: "no_snapshot" | "single_snapshot" | "short_period" | "compared"; missing: string[]; verification: string | null;
  latest_balance?: { value: number; as_of: string }; start_balance?: { value: number; as_of: string };
  window?: { from: string; to: string; months: number };
  flows?: { deposits: number | null; deposit_count: number; withdrawals: number; fees: number; transfers_in: number; transfers_out: number;
            net_documented: number; event_count: number; same_day_events: number };
  value_change?: { total: number; documented_flows: number; unexplained: number; note: string };
  return?: PaceReturnBlock;
  planned?: { monthly_deposit: number; return_pct: number; return_source: string; fee_pct: number; fee_source: string; deposits_total: number;
              value_at_comparison: number; value_deposits_only: number; value_to_date: number | null; to_date: string } | null;
  deviation?: { vs_plan: number; vs_deposits_only: number; deposits_gap: number | null } | null;
}
export interface PaceLine { source: string; monthly_deposit: number; final_nominal: number; final_real: number; series: PlSeriesRow[] }
export interface PaceView {
  schema_version: string; source: "portfolio_lab"; engine_version: string; data_basis: "self_reported"; as_of: string;
  accounts: PaceAccountRow[]; closed_accounts: number; skipped_events: number;
  consolidated: {
    accounts_compared: number; accounts_with_plan: number; accounts_without_plan: number; accounts_without_snapshot: number;
    accounts_single_snapshot: number; accounts_short_period: number; window?: { from: string; to: string };
    start_balance?: number; latest_balance?: number;
    planned?: { deposits_total: number; value_at_comparison: number; value_deposits_only: number };
    flows?: { deposits: number | null; deposits_complete: boolean; withdrawals: number; fees: number; transfers_in: number; transfers_out: number; net_documented: number };
    value_change?: { total: number; documented_flows: number; unexplained: number };
    deviation: { vs_plan: number; vs_deposits_only: number; deposits_gap: number | null } | null;
  };
  goal_level_history?: { ytd: number; ytd_plan: number; ytd_gap: number; months_elapsed: number; monthly_average: number; streak: number } | null;
  forecast: {
    applied: boolean; reason?: string; horizon_years?: number; starting_value?: number; oldest_snapshot?: string; label?: string;
    assumptions?: { annual_return_pct: number; annual_fee_pct: number; inflation_pct: number; note: string };
    lines?: { planned_pace: PaceLine | null; actual_pace: PaceLine | null; goal_history_pace: PaceLine | null };
    gaps?: Record<string, number>; actual_pace_unavailable_reason?: string | null;
    coverage?: { accounts_with_balance: number; accounts_with_planned_deposit: number; accounts_with_actual_pace: number };
  };
  course_correction: {
    applied: boolean; reason?: string; base_monthly_deposit?: number; monthly_change_to_match_planned_end?: number | null; note?: string;
    rows?: { monthly_change: number; monthly_deposit: number; final_nominal: number; delta_vs_updated_forecast: number }[];
  };
  assumptions: string[];
}
export interface PaceParams { years?: number; annual_return_pct?: number; annual_fee_pct?: number; inflation_pct?: number }
