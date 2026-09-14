import type { LeadSummary } from "../types";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

type StatusTone = "neutral" | "info" | "warning" | "success" | "danger";

// Canonical Pipeline score->color comes from the API (lead.score_color),
// derived once server-side in tma_api.py::_pipeline_temperature — no local
// threshold logic here (PIPELINE-1 remediation item 1).
const SCORE_TONE_CLASS: Record<string, string> = {
  red: "lead-pipeline-card__score--danger",
  yellow: "lead-pipeline-card__score--warning",
};

const STATUS_TONE: Record<string, StatusTone> = {
  hot: "danger",
  active: "success",
  new: "info",
  waiting_call: "warning",
};

function statusTone(status: string): StatusTone {
  return STATUS_TONE[status.toLowerCase()] ?? "neutral";
}

export function LeadCard({ lead, onClick }: { lead: LeadSummary; onClick?: () => void }) {
  return (
    <Surface
      variant="default"
      padding="none"
      className="lead-pipeline-card boss-bubble--selectable"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="lead-pipeline-card__body">
        <p className="lead-pipeline-card__name">{lead.name || "—"}</p>
        <div className="lead-pipeline-card__badges">
          <StatusBadge tone={statusTone(lead.status)}>{lead.status}</StatusBadge>
          {lead.temperature && <StatusBadge tone="neutral">{lead.temperature}</StatusBadge>}
        </div>
        {lead.next_step_label && (
          <p className="lead-pipeline-card__next">▸ {lead.next_step_label}</p>
        )}
      </div>
      <div className="lead-pipeline-card__score-wrap">
        <p className={`lead-pipeline-card__score ${SCORE_TONE_CLASS[lead.score_color] ?? ""}`}>{lead.score}</p>
        <p className="lead-pipeline-card__score-label">ציון</p>
      </div>
    </Surface>
  );
}
