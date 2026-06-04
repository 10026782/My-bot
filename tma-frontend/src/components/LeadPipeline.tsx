import { useEffect, useState } from "react";
import { fetchDashboard } from "../api";
import type { DashboardResponse, ProjectCard } from "../types";
import { LeadCard } from "./LeadCard";

interface Props {
  project: ProjectCard;
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: DashboardResponse }
  | { status: "error"; message: string };

export function LeadPipeline({ project, onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchDashboard(project.slug)
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [project.slug]);

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-blue-500 text-lg font-medium"
          aria-label="חזרה"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-900">
            {project.emoji} {project.name}
          </h1>
          <p className="text-xs text-gray-400">Lead Pipeline</p>
        </div>
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

      {state.status === "ok" && (
        <>
          {/* Summary strip */}
          <div className="flex gap-3 px-4 mb-4">
            <div className="bg-white rounded-xl px-4 py-2 shadow-sm text-center flex-1">
              <p className="text-xl font-black text-gray-900">{state.data.leads_count}</p>
              <p className="text-xs text-gray-400">לידים</p>
            </div>
            <div className="bg-white rounded-xl px-4 py-2 shadow-sm text-center flex-1">
              <p className="text-xl font-black text-gray-900">{state.data.open_tasks}</p>
              <p className="text-xs text-gray-400">משימות</p>
            </div>
            <div className="bg-white rounded-xl px-4 py-2 shadow-sm text-center flex-1">
              <p className="text-xl font-black text-gray-900">{state.data.open_deals}</p>
              <p className="text-xs text-gray-400">עסקאות</p>
            </div>
          </div>

          {/* Lead list */}
          <div className="flex flex-col gap-2 px-4">
            {state.data.leads.length === 0 ? (
              <p className="text-center text-gray-400 text-sm pt-8">אין לידים לפרויקט זה</p>
            ) : (
              state.data.leads.map((lead) => (
                <LeadCard key={lead.id} lead={lead} />
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
