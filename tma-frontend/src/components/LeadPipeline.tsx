import { useEffect, useState } from "react";
import { fetchLeads } from "../api";
import type { LeadsResponse, ProjectCard, LeadSummary } from "../types";
import { LeadCard } from "./LeadCard";
import { LeadDetail } from "./LeadDetail";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";

interface Props {
  // null = direct "All Leads" entry point (PIPELINE-1 remediation item 5),
  // not scoped to a single Projects Hub card.
  project: ProjectCard | null;
  onBack: () => void;
  authRole?: string | null;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: LeadsResponse }
  | { status: "error"; message: string };

export function LeadPipeline({ project, onBack, authRole }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [selectedLead, setSelectedLead] = useState<LeadSummary | null>(null);
  const [view, setView] = useState<string>("active");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [domainFilter, setDomainFilter] = useState<string>("");

  const baseDomain = project?.domain ?? "";
  const showDomainFilter = authRole === "owner" || authRole === "manager";

  const load = () => {
    setState({ status: "loading" });
    fetchLeads(baseDomain, { view, search })
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseDomain, view, search]);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  if (selectedLead) {
    return (
      <LeadDetail
        lead={selectedLead}
        onBack={() => setSelectedLead(null)}
        authRole={authRole}
      />
    );
  }

  const data = state.status === "ok" ? state.data : null;
  // Domain filter only makes sense when the screen isn't already scoped to
  // one Projects Hub project — the direct "All Leads" entry point.
  const visibleLeads = data
    ? (!baseDomain && domainFilter ? data.leads.filter((l) => l.domain === domainFilter) : data.leads)
    : [];

  return (
    <main className="ventures-screen lead-pipeline-screen">
      <div className="ventures-shell">
        <PageHeader
          onBack={onBack}
          eyebrow="BOSS"
          title={project ? `${project.emoji} ${project.name}` : "לידים"}
          subtitle={data ? `${visibleLeads.length} לידים` : "Lead Pipeline"}
          action={
            <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={load}>
              רענון
            </button>
          }
        />

        <div className="lead-pipeline-controls">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="חיפוש לפי שם או טלפון..."
            className="boss-input"
            aria-label="חיפוש לידים"
          />

          {data && (
            <div className="ventures-action-row" role="tablist" aria-label="תצוגות">
              {Object.entries(data.available_views).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={view === key}
                  aria-pressed={view === key}
                  onClick={() => setView(key)}
                  className="ventures-choice boss-bubble--selectable"
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {data && !baseDomain && showDomainFilter && data.available_domains.length > 0 && (
            <select
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              className="boss-select"
              aria-label="סינון לפי דומיין"
            >
              <option value="">כל הדומיינים</option>
              {data.available_domains.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          )}
        </div>

        {state.status === "loading" && (
          <ScreenState state="loading" title="טוען לידים" message="אוסף את הרשימה העדכנית…" />
        )}

        {state.status === "error" && (
          <ScreenState
            state="error"
            title="לא הצלחנו לטעון"
            message={state.message}
            action={
              <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>
                נסו שוב
              </button>
            }
          />
        )}

        {data && data.has_more && (
          <p className="lead-pipeline-banner">
            יש יותר לידים ממה שמוצג כאן — צמצם/י עם חיפוש או פילטר דומיין.
          </p>
        )}

        {data && (
          visibleLeads.length === 0 ? (
            <ScreenState state="empty" title="אין לידים להצגה" message="נסו לשנות תצוגה, חיפוש או פילטר." />
          ) : (
            <div className="lead-pipeline-list">
              {visibleLeads.map((lead) => (
                <LeadCard key={lead.id} lead={lead} onClick={() => setSelectedLead(lead)} />
              ))}
            </div>
          )
        )}
      </div>
    </main>
  );
}
