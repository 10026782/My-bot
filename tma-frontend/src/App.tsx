import { useEffect, useState } from "react";
import { fetchProjects } from "./api";
import { GlobalKpis } from "./components/GlobalKpis";
import { ProjectCard } from "./components/ProjectCard";
import { LeadPipeline } from "./components/LeadPipeline";
import { ActivityFeed } from "./components/ActivityFeed";
import { Approvals } from "./components/Approvals";
import type { ProjectsResponse, ProjectCard as TProjectCard } from "./types";

type HubState =
  | { status: "loading" }
  | { status: "ok"; data: ProjectsResponse }
  | { status: "error"; message: string };

export default function App() {
  const [hub, setHub] = useState<HubState>({ status: "loading" });
  const [selected, setSelected] = useState<TProjectCard | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [approvalsOpen, setApprovalsOpen] = useState(false);

  function loadHub() {
    setHub({ status: "loading" });
    window.Telegram?.WebApp?.ready?.();
    fetchProjects()
      .then((data) => setHub({ status: "ok", data }))
      .catch((e: unknown) =>
        setHub({ status: "error", message: String(e) })
      );
  }

  useEffect(() => { loadHub(); }, []);

  // ── Approvals view ──────────────────────────────────────────────
  if (approvalsOpen) {
    return <Approvals onBack={() => setApprovalsOpen(false)} />;
  }

  // ── Activity Feed view ──────────────────────────────────────────
  if (activityOpen) {
    return <ActivityFeed onBack={() => setActivityOpen(false)} />;
  }

  // ── Lead Pipeline view ──────────────────────────────────────────
  if (selected) {
    return (
      <LeadPipeline
        project={selected}
        onBack={() => setSelected(null)}
      />
    );
  }

  // ── Hub loading / error ─────────────────────────────────────────
  if (hub.status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (hub.status === "error") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-6 text-center">
        <p className="text-gray-600">טעינה נכשלה</p>
        <p className="text-xs text-gray-400">{hub.message}</p>
        <button
          onClick={loadHub}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium"
        >
          נסה שוב
        </button>
      </div>
    );
  }

  // ── Projects Hub ────────────────────────────────────────────────
  const { data } = hub;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center justify-between">
        <div>
          <h1 className="text-xl font-black text-gray-900">BOSS</h1>
          <p className="text-xs text-gray-400 mt-0.5">Projects Hub</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setApprovalsOpen(true)}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg"
            aria-label="אישורים"
          >
            ✅
          </button>
          <button
            onClick={() => setActivityOpen(true)}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg"
            aria-label="פעילות"
          >
            📋
          </button>
        </div>
      </div>

      <div className="mb-4">
        <GlobalKpis kpis={data.global_kpis} />
      </div>

      {data.exceptions.length > 0 && (
        <div className="mx-4 mb-4 bg-red-50 border border-red-200 rounded-xl p-3">
          {data.exceptions.map((ex, i) => (
            <p key={i} className="text-sm text-red-700">{ex}</p>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 px-4">
        {data.projects.map((card) => (
          <ProjectCard
            key={card.id}
            card={card}
            onClick={() => setSelected(card)}
          />
        ))}
      </div>
    </div>
  );
}
