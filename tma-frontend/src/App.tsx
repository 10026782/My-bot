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
import { Ventures } from "./components/Ventures";
import { MarketingStatus } from "./components/MarketingStatus";
import { MyWork } from "./components/MyWork";
import { PageHeader } from "./components/ui/PageHeader";
import { ScreenState } from "./components/ui/ScreenState";
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
  const [venturesOpen, setVenturesOpen] = useState(false);
  const [marketingOpen, setMarketingOpen] = useState(false);
  const [myWorkOpen, setMyWorkOpen] = useState(false);
  const [leadsOpen, setLeadsOpen] = useState(false);
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

  // ── Lead Pipeline — direct entry point ──────────────────────────
  // PIPELINE-1 remediation item 5: Owner/Manager/Partner all need a direct
  // frontend path to the Lead Pipeline that does not require going through
  // the owner-only Projects Hub (GET /api/projects is owner-only — Manager
  // and Partner get a 403 on it and previously had no other way in).
  // Reuses the same LeadPipeline component with project=null ("all leads
  // this identity can see") — no second Pipeline screen created.
  if (leadsOpen) {
    return (
      <LeadPipeline
        project={null}
        onBack={() => setLeadsOpen(false)}
        authRole={authRole}
      />
    );
  }

  // ── My Work ──────────────────────────────────────────────────────
  if (myWorkOpen) {
    return <MyWork onBack={() => setMyWorkOpen(false)} />;
  }

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
    return (
      <OwnerControlCenter
        onBack={() => setOwnerControlOpen(false)}
        onOpenApprovals={() => { setOwnerControlOpen(false); setApprovalsOpen(true); }}
        onOpenHealth={() => { setOwnerControlOpen(false); setHealthOpen(true); }}
        onOpenMarketing={() => { setOwnerControlOpen(false); setMarketingOpen(true); }}
        onOpenVentures={() => { setOwnerControlOpen(false); setVenturesOpen(true); }}
      />
    );
  }

  // ── Ventures view (Strategic Layer) ──────────────────────────────
  if (venturesOpen) {
    return <Ventures onBack={() => setVenturesOpen(false)} />;
  }

  if (marketingOpen) {
    return <MarketingStatus onBack={() => setMarketingOpen(false)} />;
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
      <main className="ventures-screen hub-screen">
        <div className="ventures-shell">
          <PageHeader eyebrow="BOSS" title="Projects Hub" />
          <ScreenState state="loading" title="טוען את הסקירה" message="אוסף את התמונה העדכנית…" />
        </div>
      </main>
    );
  }

  if (hub.status === "error") {
    return (
      <main className="ventures-screen hub-screen">
        <div className="ventures-shell">
          <PageHeader eyebrow="BOSS" title="Projects Hub" />
          <ScreenState
            state="error"
            title="טעינה נכשלה"
            message={hub.message}
            action={
              <div className="hub-error-actions">
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={loadHub}>
                  נסה שוב
                </button>
                {/* Projects Hub is owner-only — Manager/Partner land here on a 403.
                    Give them a direct path to the one screen they DO have access to. */}
                <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setLeadsOpen(true)}>
                  🧲 לידים
                </button>
              </div>
            }
          />
        </div>
      </main>
    );
  }

  // ── Projects Hub ────────────────────────────────────────────────
  const { data } = hub;
  const canShowOwnerControl = authRole ? authRole === "owner" : true;

  return (
    <main className="ventures-screen hub-screen">
      <div className="ventures-shell">
        <PageHeader eyebrow="BOSS" title="Projects Hub" />

        <div className="hub-quick-actions" role="toolbar" aria-label="ניווט מהיר">
          <button type="button" onClick={() => setLeadsOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="לידים">🧲</button>
          <button type="button" onClick={() => setApprovalsOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="אישורים">✅</button>
          <button type="button" onClick={() => setFinanceOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="פינאנס">💰</button>
          <button type="button" onClick={() => setPersonalOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="נכסים">🏠</button>
          <button type="button" onClick={() => setActivityOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="פעילות">📋</button>
          <button type="button" onClick={() => setDigestOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="Daily Digest">📊</button>
          <button type="button" onClick={() => setCheckinOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="צ'ק-אין יומי">✅</button>
          <button type="button" onClick={() => setGameOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="גיים">🎮</button>
          {canShowOwnerControl && (
            <button type="button" onClick={() => setOwnerControlOpen(true)} className="hub-quick-action hub-quick-action--strong boss-bubble--action" aria-label="מרכז השליטה">מרכז</button>
          )}
          {canShowOwnerControl && (
            <button type="button" onClick={() => setVenturesOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="Ventures">🔭</button>
          )}
          {canShowOwnerControl && (
            <button type="button" onClick={() => setMyWorkOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="העבודה שלי">✓</button>
          )}
          <button type="button" onClick={() => setHealthOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="בריאות מערכת">⚙️</button>
          <button type="button" onClick={() => setMarketingOpen(true)} className="hub-quick-action boss-bubble--action" aria-label="שיווק">📣</button>
        </div>

        <div className="hub-stack">
          <GlobalKpis kpis={data.global_kpis} />

          {data.exceptions.length > 0 && (
            <div className="hub-exceptions">
              {data.exceptions.map((ex, i) => (
                <p key={i}>{ex}</p>
              ))}
            </div>
          )}

          <div className="hub-projects-grid">
            {data.projects.map((card) => (
              <ProjectCard
                key={card.id}
                card={card}
                onClick={() => setSelected(card)}
              />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
