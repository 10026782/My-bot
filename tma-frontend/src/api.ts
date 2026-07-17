import type { ProjectsResponse, DashboardResponse, LeadsResponse, LeadDetail, ActivityResponse, ApprovalsResponse, FinancePulse, AssetsResponse, Asset, SystemHealth, GameToday, GameCheckin, CheckinTask, OwnerControlCenter, AuthResponse, Venture, VenturesResponse } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string) ?? "";
const DEV_ID = (import.meta.env.VITE_DEV_TELEGRAM_ID as string) ?? "";

declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?: () => void; platform?: string; version?: string } };
  }
}

function authHeaders(): Record<string, string> {
  const platform = window.Telegram?.WebApp?.platform;
  const platformHeader: Record<string, string> = platform ? { "X-TMA-Platform": platform } : {};

  if (DEV_ID) {
    return { "X-Dev-Telegram-Id": DEV_ID, ...platformHeader };
  }
  const raw = window.Telegram?.WebApp?.initData ?? "";
  if (raw) return { "X-Telegram-Init-Data": raw, ...platformHeader };
  return { ...platformHeader };
}

async function throwApiError(r: Response, fallback: string): Promise<never> {
  let message = fallback || `API ${r.status}`;
  try {
    const data = await r.json() as { error?: string; message?: string; valid?: string[] };
    const detail = data.error || data.message;
    message = detail ? `${detail}` : message;
    if (data.valid?.length) message += ` (${data.valid.join(", ")})`;
  } catch {
    try {
      const text = await r.text();
      if (text) message = text;
    } catch {
      // Keep the fallback.
    }
  }
  throw new Error(message);
}

export async function fetchProjects(): Promise<ProjectsResponse> {
  const r = await fetch(`${BASE}/api/projects`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<ProjectsResponse>;
}

export async function fetchTmaAuth(): Promise<AuthResponse | null> {
  const initData = window.Telegram?.WebApp?.initData ?? "";
  if (!initData) return null;
  const r = await fetch(`${BASE}/api/tma/auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<AuthResponse>;
}

export async function fetchDashboard(slug: string): Promise<DashboardResponse> {
  const r = await fetch(`${BASE}/api/projects/${slug}/dashboard`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<DashboardResponse>;
}

export async function fetchLeads(domain: string): Promise<LeadsResponse> {
  const r = await fetch(`${BASE}/api/leads?domain=${encodeURIComponent(domain)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<LeadsResponse>;
}

export async function fetchLead(leadId: string): Promise<LeadDetail> {
  const r = await fetch(`${BASE}/api/leads/${encodeURIComponent(leadId)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<LeadDetail>;
}

export async function askAI(contextId: string, question: string): Promise<string> {
  const r = await fetch(`${BASE}/api/ai/ask`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ context: "lead_card", context_id: contextId, question }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
  const data = await r.json() as { answer: string };
  return data.answer;
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

export async function fetchApprovals(): Promise<ApprovalsResponse> {
  const r = await fetch(`${BASE}/api/approvals`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<ApprovalsResponse>;
}

export async function actOnApproval(
  approvalId: string,
  action: "approve" | "reject",
  note?: string,
): Promise<void> {
  const r = await fetch(`${BASE}/api/approvals/${encodeURIComponent(approvalId)}`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ action, note: note ?? "" }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
}

export async function bulkApprove(): Promise<{ approved: number; skipped: number }> {
  const r = await fetch(`${BASE}/api/approvals/bulk`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<{ approved: number; skipped: number }>;
}

export async function fetchAssets(): Promise<AssetsResponse> {
  const r = await fetch(`${BASE}/api/assets`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<AssetsResponse>;
}

export async function fetchAsset(assetId: string): Promise<Asset> {
  const r = await fetch(`${BASE}/api/assets/${encodeURIComponent(assetId)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<Asset>;
}

export async function updateAsset(
  assetId: string,
  fields: Partial<{
    "Current Value": number;
    "Mortgage Balance": number;
    "Monthly Income": number;
    "Status": string;
    "Ownership %": number;
  }>,
): Promise<void> {
  const r = await fetch(`${BASE}/api/assets/${encodeURIComponent(assetId)}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
}

export async function fetchFinancePulse(): Promise<FinancePulse> {
  const r = await fetch(`${BASE}/api/finance/pulse`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<FinancePulse>;
}

export async function fetchActivity(domain?: string): Promise<ActivityResponse> {
  const params = domain ? `?domain=${encodeURIComponent(domain)}` : "";
  const r = await fetch(`${BASE}/api/activity${params}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<ActivityResponse>;
}

export async function fetchHealth(): Promise<SystemHealth> {
  const r = await fetch(`${BASE}/api/health`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<SystemHealth>;
}

export async function fetchOwnerControlCenter(): Promise<OwnerControlCenter> {
  const r = await fetch(`${BASE}/api/owner/control-center`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<OwnerControlCenter>;
}

export async function emergencyStop(action: string): Promise<void> {
  const r = await fetch(`${BASE}/api/health/emergency`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
}

export async function fetchGameToday(): Promise<GameToday> {
  const r = await fetch(`${BASE}/api/game/today`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<GameToday>;
}

export async function completeTask(taskId: string): Promise<{ ok: boolean; coins_awarded: number }> {
  const r = await fetch(`${BASE}/api/game/tasks/${encodeURIComponent(taskId)}/done`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<{ ok: boolean; coins_awarded: number }>;
}

export async function updateCheckinTaskStatus(taskId: string, status: string): Promise<void> {
  const r = await fetch(`${BASE}/api/game/checkin/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
}

export async function fetchGameCheckin(): Promise<GameCheckin> {
  const r = await fetch(`${BASE}/api/game/checkin`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<GameCheckin>;
}

export async function saveGameCheckin(
  tasks: CheckinTask[]
): Promise<{ ok: boolean; total_xp: number; updated_at: string; updated_by: string }> {
  const r = await fetch(`${BASE}/api/game/checkin`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ tasks }),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

export async function patchLead(
  leadId: string,
  fields: Partial<{
    status: string;
    score: number;
    outcome: string;
    next_followup: string;
    owner: string[];      // Airtable multipleRecordLinks — must be array of record IDs
    next_step: string;
  }>,
): Promise<void> {
  const r = await fetch(`${BASE}/api/leads/${encodeURIComponent(leadId)}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!r.ok) await throwApiError(r, `Lead update failed (${r.status})`);
}

export async function setLeadOutcome(leadId: string, outcome: string): Promise<void> {
  const r = await fetch(`${BASE}/api/leads/${encodeURIComponent(leadId)}/outcome`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ outcome }),
  });
  if (!r.ok) await throwApiError(r, `Outcome update failed (${r.status})`);
}

export async function createLeadTask(
  leadId: string,
  task: { title: string; due_date?: string; notes?: string },
): Promise<{ id: string }> {
  const r = await fetch(`${BASE}/api/leads/${encodeURIComponent(leadId)}/task`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(task),
  });
  if (!r.ok) await throwApiError(r, `Task creation failed (${r.status})`);
  return r.json() as Promise<{ id: string }>;
}

export async function fetchVentures(stage?: string): Promise<VenturesResponse> {
  const params = stage ? `?stage=${encodeURIComponent(stage)}` : "";
  const r = await fetch(`${BASE}/api/ventures${params}`, { headers: authHeaders() });
  if (!r.ok) await throwApiError(r, `API ${r.status}`);
  return r.json() as Promise<VenturesResponse>;
}

export async function fetchVenture(ventureId: string): Promise<Venture> {
  const r = await fetch(`${BASE}/api/ventures/${encodeURIComponent(ventureId)}`, { headers: authHeaders() });
  if (!r.ok) await throwApiError(r, `API ${r.status}`);
  return r.json() as Promise<Venture>;
}

export async function createVenture(
  fields: Partial<{
    name: string;
    stage: string;
    domain: string;
    conviction: string;
    estimated_potential: number;
    target_decision_date: string;
    decision_log: string;
    next_action: string;
    notes: string;
  }>,
): Promise<Venture> {
  const r = await fetch(`${BASE}/api/ventures`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!r.ok) await throwApiError(r, `Venture creation failed (${r.status})`);
  return r.json() as Promise<Venture>;
}

export async function updateVenture(
  ventureId: string,
  fields: Partial<{
    name: string;
    stage: string;
    domain: string;
    conviction: string;
    estimated_potential: number;
    target_decision_date: string;
    decision_log: string;
    next_action: string;
    notes: string;
  }>,
): Promise<void> {
  const r = await fetch(`${BASE}/api/ventures/${encodeURIComponent(ventureId)}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!r.ok) await throwApiError(r, `Venture update failed (${r.status})`);
}
