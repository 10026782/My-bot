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

