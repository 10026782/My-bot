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

export interface FccOverview {
  goals: FccGoalRow[];
  savings_release?: FccSavingsRelease | null;
  loans?: FccLoans;
  assets?: FccAssets;
  summary: Partial<Record<"income" | "savings" | "emergency_fund" | "debt_repaid" | "payment_reduction", FccSummaryCard>>;
  tasks: { id: string; title: string | null; due_date: string | null; status: string | null }[];
  monthly_cash_improvement: number;
  household?: { month_total: number };
  receipts?: { missing_count: number; missing_amount: number };
  obligations?: { total_monthly: number; flagged_count: number; flagged_monthly: number; cancel_pending?: number; potential_saving: number; count: number };
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
