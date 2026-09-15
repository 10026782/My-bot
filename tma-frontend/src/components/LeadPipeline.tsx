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

// LeadStatus (airtable_schema.py) — Hebrew labels for the status filter
// dropdown. Keep in sync with LeadStatus.ALL; a value missing here still
// renders (falls back to the raw key) rather than disappearing.
const STATUS_LABELS: Record<string, string> = {
  new: "חדש",
  waiting_call: "ממתין לשיחה",
  waiting_response: "ממתין לתגובה",
  high_confidence: "בטחון גבוה",
  active: "פעיל",
  done: "הושלם",
  archived: "בארכיון",
  lost: "אבוד",
  duplicate: "כפילות",
  not_relevant: "לא רלוונטי",
};

const TEMPERATURE_OPTIONS = ["קר", "חם", "חם מאוד"];

const DATE_RANGE_OPTIONS: { key: string; label: string }[] = [
  { key: "all", label: "הכל" },
  { key: "today", label: "היום" },
  { key: "week", label: "השבוע" },
  { key: "month", label: "החודש" },
];

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
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [nextActionFilter, setNextActionFilter] = useState<string>("");
  const [temperatureFilter, setTemperatureFilter] = useState<string>("");
  const [dateRange, setDateRange] = useState<string>("all");
  const [showFilters, setShowFilters] = useState(false);

  const baseDomain = project?.domain ?? "";
  const showDomainFilter = authRole === "owner" || authRole === "manager";
  const activeAdvancedCount = [domainFilter, sourceFilter, nextActionFilter, temperatureFilter, dateRange !== "all" ? dateRange : ""]
    .filter(Boolean).length;

  const load = () => {
    setState({ status: "loading" });
    fetchLeads(baseDomain, {
      view, search, status: statusFilter, source: sourceFilter,
      next_action: nextActionFilter, temperature: temperatureFilter, date_range: dateRange,
    })
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseDomain, view, search, statusFilter, sourceFilter, nextActionFilter, temperatureFilter, dateRange]);

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
            placeholder="חיפוש בלידים..."
            className="boss-input"
            aria-label="חיפוש בלידים"
          />

          {/* Row 1: the view buckets (formula-filtered, cheap) + a couple of
              the most common quick filters as one-tap chips, ending with a
              toggle into the full advanced panel — not a wall of buttons
              (owner decision, 15/09/2026). Search and every filter below
              combine (AND), they never replace each other. */}
          {data && (
            <div className="ventures-action-row" role="tablist" aria-label="תצוגות וסינון מהיר">
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
              <button
                type="button"
                role="tab"
                aria-selected={statusFilter === "new"}
                aria-pressed={statusFilter === "new"}
                onClick={() => setStatusFilter(statusFilter === "new" ? "" : "new")}
                className="ventures-choice boss-bubble--selectable"
              >
                חדשים
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={nextActionFilter === "Call Back"}
                aria-pressed={nextActionFilter === "Call Back"}
                onClick={() => setNextActionFilter(nextActionFilter === "Call Back" ? "" : "Call Back")}
                className="ventures-choice boss-bubble--selectable"
              >
                לחזור אליהם
              </button>
              <button
                type="button"
                aria-pressed={showFilters}
                onClick={() => setShowFilters((v) => !v)}
                className="ventures-choice boss-bubble--selectable"
              >
                ⚙️ סינון{activeAdvancedCount > 0 ? ` (${activeAdvancedCount})` : ""}
              </button>
            </div>
          )}

          {showFilters && (
            <div className="lead-pipeline-advanced-filters">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="boss-select"
                aria-label="סינון לפי סטטוס"
              >
                <option value="">כל הסטטוסים</option>
                {Object.entries(STATUS_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>

              {data && data.next_action_options.length > 0 && (
                <select
                  value={nextActionFilter}
                  onChange={(e) => setNextActionFilter(e.target.value)}
                  className="boss-select"
                  aria-label="סינון לפי Next Action"
                >
                  <option value="">כל הפעולות</option>
                  {data.next_action_options.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              )}

              {data && data.available_sources.length > 0 && (
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="boss-select"
                  aria-label="סינון לפי מקור"
                >
                  <option value="">כל המקורות</option>
                  {data.available_sources.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
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

              <select
                value={temperatureFilter}
                onChange={(e) => setTemperatureFilter(e.target.value)}
                className="boss-select"
                aria-label="סינון לפי טמפרטורה"
              >
                <option value="">כל הטמפרטורות</option>
                {TEMPERATURE_OPTIONS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>

              <div className="ventures-action-row" role="tablist" aria-label="טווח תאריכים">
                {DATE_RANGE_OPTIONS.map(({ key, label }) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={dateRange === key}
                    aria-pressed={dateRange === key}
                    onClick={() => setDateRange(key)}
                    className="ventures-choice boss-bubble--selectable"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
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
            יש יותר לידים ממה שמוצג כאן — צמצם/י עם חיפוש או פילטר.
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
