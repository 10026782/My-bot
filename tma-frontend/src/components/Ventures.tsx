import { useEffect, useRef, useState } from "react";
import { fetchVentures, fetchVenture, createVenture, updateVenture } from "../api";
import type { Venture, VenturesResponse } from "../types";

interface Props {
  onBack: () => void;
}

type ListState =
  | { status: "loading" }
  | { status: "ok"; data: VenturesResponse }
  | { status: "error"; message: string };

type DetailState =
  | { status: "loading" }
  | { status: "ok"; data: Venture }
  | { status: "error"; message: string };

type Toast = { type: "ok" | "err"; text: string };

const STAGES = [
  "Research", "Supplier/Source Contact", "Due Diligence", "Legal/Tax Review",
  "Smoke Test", "GO", "NO-GO", "Converted",
];

const STAGE_ICON: Record<string, string> = {
  "Research": "🔍",
  "Supplier/Source Contact": "🤝",
  "Due Diligence": "🕵️",
  "Legal/Tax Review": "⚖️",
  "Smoke Test": "🧪",
  "GO": "✅",
  "NO-GO": "🛑",
  "Converted": "🚀",
};

const STAGE_COLOR: Record<string, string> = {
  "Research": "bg-gray-100 text-gray-700",
  "Supplier/Source Contact": "bg-blue-100 text-blue-700",
  "Due Diligence": "bg-yellow-100 text-yellow-700",
  "Legal/Tax Review": "bg-purple-100 text-purple-700",
  "Smoke Test": "bg-orange-100 text-orange-700",
  "GO": "bg-green-100 text-green-700",
  "NO-GO": "bg-red-100 text-red-700",
  "Converted": "bg-emerald-100 text-emerald-700",
};

const CONVICTION_COLOR: Record<string, string> = {
  Low: "text-gray-400",
  Medium: "text-yellow-600",
  High: "text-green-600",
};

const DOMAINS = ["Real Estate", "Import", "SaaS", "Recruitment", "General"];
const CONVICTIONS = ["Low", "Medium", "High"];

function fmt(n: number): string {
  if (!n) return "—";
  if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `₪${Math.round(n / 1_000).toLocaleString("he-IL")}K`;
  return `₪${n.toLocaleString("he-IL")}`;
}

function stageIcon(s: string) { return STAGE_ICON[s] ?? "❔"; }
function stageBadge(s: string) { return STAGE_COLOR[s] ?? "bg-gray-100 text-gray-600"; }

// ── Venture Detail ──────────────────────────────────────────────

function VentureDetail({ ventureId, onBack }: { ventureId: string; onBack: () => void }) {
  const [state, setState] = useState<DetailState>({ status: "loading" });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [editStage, setEditStage] = useState("");
  const [editConviction, setEditConviction] = useState("");
  const [editNextAction, setEditNextAction] = useState("");
  const [editNotes, setEditNotes] = useState("");

  useEffect(() => {
    fetchVenture(ventureId)
      .then((data) => {
        setState({ status: "ok", data });
        setEditStage(data.stage);
        setEditConviction(data.conviction);
        setEditNextAction(data.next_action);
        setEditNotes(data.notes);
      })
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [ventureId]);

  function showToast(type: "ok" | "err", text: string) {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast({ type, text });
    timerRef.current = setTimeout(() => setToast(null), 2500);
  }

  async function handleSave() {
    if (state.status !== "ok" || saving) return;
    setSaving(true);
    try {
      const d = state.data;
      const fields: Parameters<typeof updateVenture>[1] = {};
      if (editStage && editStage !== d.stage) fields.stage = editStage;
      if (editConviction && editConviction !== d.conviction) fields.conviction = editConviction;
      if (editNextAction !== d.next_action) fields.next_action = editNextAction;
      if (editNotes !== d.notes) fields.notes = editNotes;

      if (Object.keys(fields).length === 0) { showToast("ok", "אין שינויים"); return; }
      await updateVenture(ventureId, fields);
      showToast("ok", "נשמר ✓");
      const updated = await fetchVenture(ventureId);
      setState({ status: "ok", data: updated });
      setEditStage(updated.stage);
      setEditConviction(updated.conviction);
      setEditNextAction(updated.next_action);
      setEditNotes(updated.notes);
    } catch {
      showToast("err", "שמירה נכשלה");
    } finally {
      setSaving(false);
    }
  }

  const d = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-56">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none">←</button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-black text-gray-900 truncate">
            {d ? `${stageIcon(d.stage)} ${d.name}` : "Venture"}
          </h1>
          <p className="text-xs text-gray-400">{d?.domain || "Venture Card"}</p>
        </div>
        {d?.stage && (
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${stageBadge(d.stage)}`}>
            {d.stage}
          </span>
        )}
      </div>

      {toast && (
        <div className={`fixed top-4 left-4 right-4 z-50 rounded-xl px-4 py-3 text-sm font-medium shadow-lg text-center
          ${toast.type === "ok" ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
          {toast.text}
        </div>
      )}

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {state.status === "error" && (
        <div className="mx-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{state.message}</div>
      )}

      {d && (
        <div className="flex flex-col gap-3 px-4">
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-gray-400 mb-3">פרטים</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              <div>
                <p className="text-[10px] text-gray-400">פוטנציאל משוער</p>
                <p className="text-base font-bold text-gray-900">{fmt(d.estimated_potential)}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">ביטחון</p>
                <p className={`text-base font-bold ${CONVICTION_COLOR[d.conviction] ?? "text-gray-600"}`}>{d.conviction || "—"}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">תאריך החלטה משוער</p>
                <p className="text-sm font-semibold text-gray-700">{d.target_decision_date || "—"}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">תחום</p>
                <p className="text-sm font-semibold text-gray-700">{d.domain || "—"}</p>
              </div>
            </div>
          </div>

          {d.decision_log && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-2">Decision Log</p>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{d.decision_log}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Fixed action bar ── */}
      {d && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 pt-3 pb-4 flex flex-col gap-2.5 shadow-xl">
          {/* Stage chips */}
          <div className="flex gap-1.5 overflow-x-auto">
            {STAGES.map((s) => (
              <button
                key={s}
                onClick={() => setEditStage(s)}
                className={`flex-shrink-0 text-[11px] px-2.5 py-1.5 rounded-full font-medium transition-all
                  ${editStage === s ? "bg-blue-500 text-white shadow" : stageBadge(s)}`}
              >
                {stageIcon(s)} {s}
              </button>
            ))}
          </div>
          {/* Conviction chips */}
          <div className="flex gap-2">
            {CONVICTIONS.map((c) => (
              <button
                key={c}
                onClick={() => setEditConviction(c)}
                className={`flex-1 text-xs py-1.5 rounded-full font-medium transition-all
                  ${editConviction === c ? "bg-blue-500 text-white shadow" : "bg-gray-100 text-gray-600"}`}
              >
                {c}
              </button>
            ))}
          </div>
          {/* Next action */}
          <input type="text" value={editNextAction} onChange={(e) => setEditNextAction(e.target.value)}
            placeholder="הצעד הבא" className="bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400" />
          {/* Notes + Save */}
          <div className="flex gap-2">
            <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)}
              placeholder="הערות" className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400" />
            <button onClick={handleSave} disabled={saving}
              className="bg-blue-500 text-white rounded-xl px-5 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70">
              {saving ? "…" : "שמור"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── New Venture form ─────────────────────────────────────────────

function NewVentureForm({ onCreated, onCancel }: { onCreated: (v: Venture) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState(DOMAINS[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    if (!name.trim() || saving) return;
    setSaving(true);
    setError("");
    try {
      const v = await createVenture({ name: name.trim(), domain });
      onCreated(v);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-end" onClick={onCancel}>
      <div className="bg-white rounded-t-2xl w-full p-4 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-bold text-gray-900">🔭 Venture חדש</h2>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)}
          placeholder="שם ההזדמנות" className="bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400" />
        <div className="flex gap-2 overflow-x-auto">
          {DOMAINS.map((dm) => (
            <button
              key={dm}
              onClick={() => setDomain(dm)}
              className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition-all
                ${domain === dm ? "bg-blue-500 text-white shadow" : "bg-gray-100 text-gray-600"}`}
            >
              {dm}
            </button>
          ))}
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div className="flex gap-2">
          <button onClick={onCancel} className="flex-1 bg-gray-100 text-gray-600 rounded-xl py-2 text-sm font-medium">ביטול</button>
          <button onClick={handleCreate} disabled={saving || !name.trim()}
            className="flex-1 bg-blue-500 text-white rounded-xl py-2 text-sm font-medium disabled:opacity-40">
            {saving ? "…" : "צור"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Ventures Overview ────────────────────────────────────────────

export function Ventures({ onBack }: Props) {
  const [state, setState] = useState<ListState>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<string>("");
  const [showNew, setShowNew] = useState(false);

  function load(stage?: string) {
    setState({ status: "loading" });
    fetchVentures(stage)
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }

  useEffect(() => { load(); }, []);

  if (selectedId) {
    return (
      <VentureDetail
        ventureId={selectedId}
        onBack={() => { setSelectedId(null); load(stageFilter || undefined); }}
      />
    );
  }

  const d = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none">←</button>
        <div className="flex-1">
          <h1 className="text-lg font-black text-gray-900">🔭 Ventures</h1>
          <p className="text-xs text-gray-400">
            {d ? `${d.count} הזדמנויות` : "Strategic Layer"}
          </p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="bg-blue-500 text-white rounded-full px-3 py-1.5 text-xs font-medium active:opacity-70">
          + חדש
        </button>
      </div>

      {/* Stage filter chips */}
      <div className="flex gap-1.5 overflow-x-auto px-4 mb-3">
        <button
          onClick={() => { setStageFilter(""); load(); }}
          className={`flex-shrink-0 text-[11px] px-2.5 py-1.5 rounded-full font-medium transition-all
            ${stageFilter === "" ? "bg-blue-500 text-white shadow" : "bg-gray-200 text-gray-600"}`}
        >
          הכל
        </button>
        {STAGES.map((s) => (
          <button
            key={s}
            onClick={() => { setStageFilter(s); load(s); }}
            className={`flex-shrink-0 text-[11px] px-2.5 py-1.5 rounded-full font-medium transition-all
              ${stageFilter === s ? "bg-blue-500 text-white shadow" : stageBadge(s)}`}
          >
            {stageIcon(s)} {s}
          </button>
        ))}
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {state.status === "error" && (
        <div className="mx-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{state.message}</div>
      )}

      {d && (
        <div className="flex flex-col gap-3 px-4">
          {d.ventures.length === 0 ? (
            <p className="text-center text-gray-400 text-sm pt-8">אין הזדמנויות רשומות</p>
          ) : (
            d.ventures.map((v) => (
              <div
                key={v.id}
                className="bg-white rounded-xl shadow-sm p-4 active:opacity-70 cursor-pointer"
                onClick={() => setSelectedId(v.id)}
              >
                <div className="flex items-start gap-3">
                  <div className="text-2xl flex-shrink-0 mt-0.5">{stageIcon(v.stage)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-gray-900 truncate">{v.name || "—"}</p>
                      {v.estimated_potential > 0 && (
                        <p className="text-sm font-bold text-gray-900 flex-shrink-0">{fmt(v.estimated_potential)}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {v.domain && <span className="text-[10px] text-gray-400">{v.domain}</span>}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${stageBadge(v.stage)}`}>
                        {v.stage}
                      </span>
                      {v.conviction && (
                        <span className={`text-[10px] font-bold ${CONVICTION_COLOR[v.conviction] ?? "text-gray-400"}`}>
                          {v.conviction}
                        </span>
                      )}
                    </div>
                    {v.next_action && (
                      <p className="text-xs text-gray-500 mt-1.5 truncate">→ {v.next_action}</p>
                    )}
                    {v.target_decision_date && (
                      <p className="text-[10px] text-gray-400 mt-0.5">🎯 {v.target_decision_date}</p>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {showNew && (
        <NewVentureForm
          onCancel={() => setShowNew(false)}
          onCreated={(v) => { setShowNew(false); setSelectedId(v.id); }}
        />
      )}
    </div>
  );
}
