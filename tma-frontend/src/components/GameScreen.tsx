import { useEffect, useState } from "react";
import { fetchGameToday, completeTask } from "../api";
import type { GameToday, DailyTask } from "../types";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: GameToday }
  | { status: "error"; message: string };

function isCompletedStatus(status: DailyTask["status"] | string): boolean {
  const normalized = String(status || "").trim().toLowerCase();
  return normalized === "done" || normalized === "completed";
}

function isSkippedStatus(status: DailyTask["status"] | string): boolean {
  return String(status || "").trim().toLowerCase() === "skipped";
}

function hasDisplayableTask(task: DailyTask): boolean {
  return Boolean((task.task || "").trim()) || Number(task.coins || 0) > 0;
}

function WorldBar({ world }: { world: NonNullable<GameToday["world"]> }) {
  const pct    = Math.round(world.progress_pct);
  const filled = Math.round(pct / 10);
  const bar    = "█".repeat(filled) + "░".repeat(10 - filled);

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
        World {world.number}
      </p>
      <p className="text-base font-bold text-gray-900">{world.name}</p>
      <div className="mt-2">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span className="font-mono text-green-600">{bar}</span>
          <span className="font-semibold">{pct}%</span>
        </div>
        <div className="flex justify-between text-xs text-gray-400">
          <span>{world.coins_earned}🪙 מתוך {world.coins_target}</span>
          {world.prize && <span>🏆 {world.prize}</span>}
        </div>
      </div>
    </div>
  );
}

function TaskRow({
  task,
  index,
  completing,
  onComplete,
}: {
  task: DailyTask;
  index: number;
  completing: boolean;
  onComplete: () => void;
}) {
  const isDone    = isCompletedStatus(task.status);
  const isSkipped = isSkippedStatus(task.status);

  return (
    <div className={`bg-white rounded-xl shadow-sm p-4 flex items-center gap-3 ${isDone ? "opacity-70" : ""}`}>
      <span className="text-gray-400 text-xs font-bold w-5 flex-shrink-0 text-center">{index}.</span>
      <span className="text-xl flex-shrink-0">
        {isDone ? "☑" : isSkipped ? "⏭️" : "☐"}
      </span>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold leading-snug ${isDone ? "line-through text-gray-400" : "text-gray-900"}`}>
          {task.task}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] bg-yellow-50 text-yellow-700 px-1.5 py-0.5 rounded-full font-bold">
            {task.coins}🪙
          </span>
          {task.who && (
            <span className="text-[10px] text-gray-400">{task.who}</span>
          )}
        </div>
      </div>
      {isDone ? (
        <span className="text-xl flex-shrink-0">✅</span>
      ) : isSkipped ? null : (
        <button
          onClick={onComplete}
          disabled={completing}
          className="flex-shrink-0 px-3 h-9 flex items-center justify-center rounded-full bg-blue-50 text-blue-700 active:bg-blue-100 disabled:opacity-40 text-xs font-bold"
          aria-label="סמן כהושלם"
        >
          {completing ? "…" : "Done"}
        </button>
      )}
    </div>
  );
}

export function GameScreen({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [completing, setCompleting] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  }

  function load() {
    setState({ status: "loading" });
    fetchGameToday()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }

  useEffect(() => { load(); }, []);

  async function handleComplete(task: DailyTask) {
    if (isCompletedStatus(task.status) || completing) return;

    // Optimistic update
    if (state.status === "ok") {
      const prev = state.data;
      setState({
        status: "ok",
        data: {
          ...prev,
          tasks: prev.tasks.map((t) =>
            t.id === task.id ? { ...t, status: "Done" as const } : t
          ),
          total_coins: prev.total_coins + task.coins,
        },
      });
    }

    setCompleting(task.id);
    try {
      await completeTask(task.id);
    } catch {
      load(); // revert optimistic update
      showToast("⚠️ שגיאה בשמירה — נסה שוב");
    } finally {
      setCompleting(null);
    }
  }

  const today = new Date();
  const dateLabel = `${today.getDate()}.${today.getMonth() + 1}`;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none" aria-label="חזרה">←</button>
        <div>
          <h1 className="text-lg font-black text-gray-900">🎮 Game</h1>
          <p className="text-xs text-gray-400">{dateLabel}</p>
        </div>
        <button onClick={load} className="mr-auto text-gray-400 text-sm active:text-gray-600">רענן</button>
      </div>

      {/* Error toast */}
      {toast && (
        <div className="mx-4 mt-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 font-medium shadow-sm">
          {toast}
        </div>
      )}

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

      {state.status === "ok" && (() => {
        const data = {
          ...state.data,
          tasks: state.data.tasks.filter(hasDisplayableTask),
        };
        const openCount = data.tasks.filter((t) => !isCompletedStatus(t.status) && !isSkippedStatus(t.status)).length;
        const doneCount = data.tasks.filter((t) => isCompletedStatus(t.status)).length;

        return (
          <div className="flex flex-col gap-3 px-4">

            {/* World progress */}
            {data.world && <WorldBar world={data.world} />}

            {/* Quest Log */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                  Quest Log היום
                </p>
                <p className="text-xs text-gray-400">
                  {doneCount}/{data.tasks.length} הושלם
                </p>
              </div>
              {data.tasks.length === 0 ? (
                <p className="text-sm text-gray-400 py-2">אין משימות להיום.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {data.tasks.map((task, i) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      index={i + 1}
                      completing={completing === task.id}
                      onComplete={() => handleComplete(task)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Total coins */}
            <div className="bg-white rounded-xl shadow-sm p-4 flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-700">סה״כ מטבעות</p>
              <p className="text-xl font-black text-yellow-600">{data.total_coins}🪙</p>
            </div>

            {openCount === 0 && data.tasks.length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
                <p className="text-base font-bold text-green-700">🏆 כל המשימות הושלמו!</p>
              </div>
            )}

          </div>
        );
      })()}
    </div>
  );
}
