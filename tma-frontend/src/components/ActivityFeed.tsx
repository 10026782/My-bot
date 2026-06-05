import { useEffect, useState } from "react";
import { fetchActivity } from "../api";
import type { ActivityEntry, ActivityResponse } from "../types";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: ActivityResponse }
  | { status: "error"; message: string };

const CHANNEL_ICON: Record<string, string> = {
  whatsapp: "💬",
  telegram: "✈️",
  email:    "📧",
  voice:    "🎙️",
  tma:      "📱",
};

const SENTIMENT_COLOR: Record<string, string> = {
  positive: "text-green-500",
  negative: "text-red-500",
  neutral:  "text-gray-400",
};

function channelIcon(ch: string) {
  return CHANNEL_ICON[ch?.toLowerCase()] ?? "💼";
}

function relativeTime(ts: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts.slice(0, 10);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `לפני ${mins} דקות`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `לפני ${hrs} שעות`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "אתמול";
  if (days < 7) return `לפני ${days} ימים`;
  return d.toLocaleDateString("he-IL", { day: "numeric", month: "short" });
}

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  const label = entry.title || entry.summary?.slice(0, 60) || "—";
  const sub   = entry.title && entry.summary ? entry.summary.slice(0, 80) : "";

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 flex gap-3">
      <div className="text-2xl flex-shrink-0 mt-0.5">{channelIcon(entry.channel)}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 leading-snug">{label}</p>
        {sub && <p className="text-xs text-gray-500 mt-0.5 leading-snug line-clamp-2">{sub}</p>}
        <div className="flex items-center gap-2 mt-1.5">
          {entry.domain && (
            <span className="text-[10px] bg-blue-50 text-blue-500 px-1.5 py-0.5 rounded-full font-medium">
              {entry.domain.replace("_", " ")}
            </span>
          )}
          {entry.timestamp && (
            <span className="text-[10px] text-gray-400">{relativeTime(entry.timestamp)}</span>
          )}
          {entry.sentiment && (
            <span className={`text-[10px] font-medium ${SENTIMENT_COLOR[entry.sentiment] ?? "text-gray-400"}`}>
              {entry.sentiment}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function ActivityFeed({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchActivity()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, []);

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
          <h1 className="text-lg font-black text-gray-900">פעילות</h1>
          <p className="text-xs text-gray-400">
            {state.status === "ok" ? `${state.data.count} רשומות` : "Activity Feed"}
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
          {state.data.entries.length === 0 ? (
            <p className="text-center text-gray-400 text-sm pt-8">אין פעילות עדיין</p>
          ) : (
            state.data.entries.map((entry) => (
              <ActivityRow key={entry.id} entry={entry} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
