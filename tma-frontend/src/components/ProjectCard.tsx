import type { ProjectCard as TProjectCard } from "../types";

const COLOR_CLASS: Record<string, string> = {
  red:    "border-red-500",
  yellow: "border-yellow-400",
  green:  "border-green-500",
};

const DOT_CLASS: Record<string, string> = {
  red:    "bg-red-500",
  yellow: "bg-yellow-400",
  green:  "bg-green-500",
};

export function ProjectCard({ card, onClick }: { card: TProjectCard; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className={`rounded-2xl border-r-4 bg-white shadow-sm p-4 flex flex-col gap-1 cursor-pointer active:opacity-70 ${COLOR_CLASS[card.status_color] ?? "border-gray-300"}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-2xl">{card.emoji}</span>
        <span className={`w-2.5 h-2.5 rounded-full ${DOT_CLASS[card.status_color] ?? "bg-gray-300"}`} />
      </div>
      <div className="font-bold text-base text-gray-800 mt-1">{card.name}</div>
      <div className="text-3xl font-black text-gray-900 leading-none">{card.kpi.value}</div>
      <div className="text-xs text-gray-400">{card.kpi.label}</div>
      {card.exception && (
        <div className="text-xs text-red-500 font-medium mt-1">{card.exception}</div>
      )}
    </div>
  );
}
