import { useEffect, useState } from "react";
import { fetchLeads } from "../api";
import type { LeadsResponse, ProjectCard } from "../types";
import { LeadCard } from "./LeadCard";

interface Props {
  project: ProjectCard;
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: LeadsResponse }
  | { status: "error"; message: string };

export function LeadPipeline({ project, onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchLeads(project.slug)
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [project.slug]);

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
            {project.emoji} {project.name}
          </h1>
          <p className="text-xs text-gray-400">
            {state.status === "ok" ? `${state.data.count} לידים` : "Lead Pipeline"}
          </p>
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
        <div className="flex flex-col gap-2 px-4">
          {state.data.leads.length === 0 ? (
            <p className="text-center text-gray-400 text-sm pt-8">אין לידים לפרויקט זה</p>
          ) : (
            state.data.leads.map((lead) => (
              <LeadCard key={lead.id} lead={lead} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
