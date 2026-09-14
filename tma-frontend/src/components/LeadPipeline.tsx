import { useEffect, useState } from "react";
import { fetchLeads } from "../api";
import type { LeadsResponse, ProjectCard, LeadSummary } from "../types";
import { LeadCard } from "./LeadCard";
import { LeadDetail } from "./LeadDetail";

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

  useEffect(() => {
    setState({ status: "loading" });
    fetchLeads(baseDomain, { view, search })
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
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
    <div className="min-h-screen bg-gray-100 pb-8">
      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-blue-500 text-xl font-medium leading-none"
          aria-label="חזרה"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-900">
            {project ? `${project.emoji} ${project.name}` : "🧲 לידים"}
          </h1>
          <p className="text-xs text-gray-400">
            {data ? `${visibleLeads.length} לידים` : "Lead Pipeline"}
          </p>
        </div>
      </div>

      <div className="px-4 mb-3 flex flex-col gap-2">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="חיפוש לפי שם או טלפון..."
          className="bg-white rounded-xl px-3 py-2 text-sm outline-none shadow-sm placeholder-gray-400"
        />

        {data && (
          <div className="flex gap-2 overflow-x-auto">
            {Object.entries(data.available_views).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setView(key)}
                className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium ${
                  view === key ? "bg-blue-500 text-white" : "bg-white text-gray-600 shadow-sm"
                }`}
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
            className="bg-white rounded-xl px-3 py-2 text-sm outline-none shadow-sm"
          >
            <option value="">כל הדומיינים</option>
            {data.available_domains.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        )}
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {state.status === "error" && (
        <div className="mx-4 mt-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {state.message}
        </div>
      )}

      {data && data.has_more && (
        <div className="mx-4 mb-3 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-700">
          יש יותר לידים ממה שמוצג כאן — צמצם/י עם חיפוש או פילטר דומיין.
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-2 px-4">
          {visibleLeads.length === 0 ? (
            <p className="text-center text-gray-400 text-sm pt-8">אין לידים להצגה</p>
          ) : (
            visibleLeads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                onClick={() => setSelectedLead(lead)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
