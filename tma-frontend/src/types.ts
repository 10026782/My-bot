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
  income_this_month: number;
  pending_payments_count: number;
  pending_payments_amount: number;
  overdue_tasks: number;
  hot_leads_count: number;
}

export interface ProjectsResponse {
  global_kpis: GlobalKpis;
  exceptions: string[];
  projects: ProjectCard[];
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
  domain: string;
  source: string;
}

export interface LeadsResponse {
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

export interface LeadDetail {
  id: string;
  name: string;
  phone: string;
  domain: string;
  status: string;
  score: number;
  score_color: "red" | "yellow" | "blue";
  source: string;
  summary: string;
  next_step: string;
  created_at: string;
  timeline: TimelineEntry[];
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

