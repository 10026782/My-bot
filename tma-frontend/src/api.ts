import type { ProjectsResponse, DashboardResponse, LeadsResponse, LeadDetail } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string) ?? "";
const DEV_ID = (import.meta.env.VITE_DEV_TELEGRAM_ID as string) ?? "";

declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?: () => void } };
  }
}

function authHeaders(): Record<string, string> {
  if (DEV_ID) {
    return { "X-Dev-Telegram-Id": DEV_ID };
  }
  const raw = window.Telegram?.WebApp?.initData ?? "";
  if (raw) return { "X-Telegram-Init-Data": raw };
  return {};
}

export async function fetchProjects(): Promise<ProjectsResponse> {
  const r = await fetch(`${BASE}/api/projects`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<ProjectsResponse>;
}

export async function fetchDashboard(slug: string): Promise<DashboardResponse> {
  const r = await fetch(`${BASE}/api/projects/${slug}/dashboard`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<DashboardResponse>;
}

export async function fetchLeads(slug: string): Promise<LeadsResponse> {
  const r = await fetch(`${BASE}/api/leads?project_slug=${encodeURIComponent(slug)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<LeadsResponse>;
}

export async function fetchLead(leadId: string): Promise<LeadDetail> {
  const r = await fetch(`${BASE}/api/leads/${encodeURIComponent(leadId)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<LeadDetail>;
}

export async function updateLeadStatus(leadId: string, status: string): Promise<void> {
  const r = await fetch(`${BASE}/api/leads/${encodeURIComponent(leadId)}/status`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
}

export async function createFollowup(leadId: string, note: string): Promise<void> {
  const r = await fetch(`${BASE}/api/followup`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId, note }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
}
