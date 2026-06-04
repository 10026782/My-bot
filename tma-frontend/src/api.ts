import type { ProjectsResponse, DashboardResponse } from "./types";

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
