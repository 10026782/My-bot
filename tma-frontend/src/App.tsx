import { useEffect, useState } from "react";
import { fetchProjects, fetchTmaAuth } from "./api";
import { GlobalKpis } from "./components/GlobalKpis";
import { ProjectCard } from "./components/ProjectCard";
import { LeadPipeline } from "./components/LeadPipeline";
import { ActivityFeed } from "./components/ActivityFeed";
import { Approvals } from "./components/Approvals";
import { FinancePulse } from "./components/FinancePulse";
import { PersonalMode } from "./components/PersonalMode";
import { SystemHealth } from "./components/SystemHealth";
import { GameScreen } from "./components/GameScreen";
import { BossCheckin } from "./components/BossCheckin";
import { BossDigest } from "./components/BossDigest";
import { OwnerControlCenter } from "./components/OwnerControlCenter";
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
  const [financeOpen, setFinanceOpen] = useState(false);
  const [personalOpen, setPersonalOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const [gameOpen, setGameOpen] = useState(false);
  const [checkinOpen, setCheckinOpen] = useState(false);
  const [digestOpen,  setDigestOpen]  = useState(false);
  const [ownerControlOpen, setOwnerControlOpen] = useState(false);
  const [authRole, setAuthRole] = useState<string | null>(null);

  function loadHub() {
    setHub({ status: "loading" });
    window.Telegram?.WebApp?.ready?.();
    fetchProjects()
      .then((data) => setHub({ status: "ok", data }))
      .catch((e: unknown) =>
        setHub({ status: "error", message: String(e) })
      );
  }

  useEffect(() => {
    loadHub();
    fetchTmaAuth()
      .then((auth) => {
        if (auth?.role) setAuthRole(auth.role);
      })
      .catch(() => setAuthRole(null));
  }, []);

  // ── Boss Daily Check-in ─────────────────────────────────────────
  if (checkinOpen) {
    return <BossCheckin onBack={() => setCheckinOpen(false)} />;
  }

  // ── Boss Daily Digest ───────────────────────────────────────────
  if (digestOpen) {
    return <BossDigest onBack={() => setDigestOpen(false)} />;
  }

  // ── Game view ───────────────────────────────────────────────────
  if (gameOpen) {
    return <GameScreen onBack={() => setGameOpen(false)} />;
  }

  if (ownerControlOpen) {
    return <OwnerControlCenter onBack={() => setOwnerControlOpen(false)} />;
  }

  // ── System Health view ──────────────────────────────────────────
  if (healthOpen) {
    return <SystemHealth onBack={() => setHealthOpen(false)} />;
  }

  // ── Personal Mode view ──────────────────────────────────────────
  if (personalOpen) {
    return <PersonalMode onBack={() => setPersonalOpen(false)} />;
  }

  // ── Finance Pulse view ──────────────────────────────────────────
  if (financeOpen) {
    return <FinancePulse onBack={() => setFinanceOpen(false)} />;
  }

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
        authRole={authRole}
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
  const canShowOwnerControl = authRole ? authRole === "owner" : true;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center justify-between">
        <div>
          <h1 className="text-xl font-black text-gray-900">BOSS</h1>
          <p className="text-xs text-gray-400 mt-0.5">Projects Hub</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setApprovalsOpen(true)}  className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="אישורים">✅</button>
          <button onClick={() => setFinanceOpen(true)}    className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="פינאנס">💰</button>
          <button onClick={() => setPersonalOpen(true)}   className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="נכסים">🏠</button>
          <button onClick={() => setActivityOpen(true)}   className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="פעילות">📋</button>
          <button onClick={() => setDigestOpen(true)}    className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="Daily Digest">📊</button>
          <button onClick={() => setCheckinOpen(true)}   className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="צ'ק-אין יומי">✅</button>
          <button onClick={() => setGameOpen(true)}      className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="גיים">🎮</button>
          {canShowOwnerControl && (
            <button onClick={() => setOwnerControlOpen(true)} className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-900 text-white active:bg-gray-700 text-xs font-black" aria-label="Owner Control Center">OC</button>
          )}
          <button onClick={() => setHealthOpen(true)}    className="w-9 h-9 flex items-center justify-center rounded-full bg-gray-100 text-gray-500 active:bg-gray-200 text-lg" aria-label="בריאות מערכת">⚙️</button>
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
