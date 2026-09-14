import type { ProjectCard as TProjectCard } from "../types";
import { Surface } from "./ui/Surface";

const BORDER_CLASS: Record<string, string> = {
  red: "hub-project-card--red",
  yellow: "hub-project-card--yellow",
  green: "hub-project-card--green",
};

const DOT_CLASS: Record<string, string> = {
  red: "hub-project-card__dot--red",
  yellow: "hub-project-card__dot--yellow",
  green: "hub-project-card__dot--green",
};

export function ProjectCard({ card, onClick }: { card: TProjectCard; onClick: () => void }) {
  return (
    <Surface
      padding="comfortable"
      className={`hub-project-card boss-bubble--selectable ${BORDER_CLASS[card.status_color] ?? ""}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="hub-project-card__top">
        <span className="hub-project-card__emoji">{card.emoji}</span>
        <span className={`hub-project-card__dot ${DOT_CLASS[card.status_color] ?? ""}`} />
      </div>
      <p className="hub-project-card__name">{card.name}</p>
      <p className="hub-project-card__value">{card.kpi.value}</p>
      <p className="hub-project-card__label">{card.kpi.label}</p>
      {card.exception && <p className="hub-project-card__exception">{card.exception}</p>}
    </Surface>
  );
}
