import { useEffect, useRef, useState } from "react";
import { fetchAssets, fetchAsset, updateAsset } from "../api";
import type { Asset, AssetsResponse } from "../types";

interface Props {
  onBack: () => void;
}

type ListState =
  | { status: "loading" }
  | { status: "ok"; data: AssetsResponse }
  | { status: "error"; message: string };

type DetailState =
  | { status: "loading" }
  | { status: "ok"; data: Asset }
  | { status: "error"; message: string };

type Toast = { type: "ok" | "err"; text: string };

const TYPE_ICON: Record<string, string> = {
  דירה:    "🏠",
  קרקע:   "🌿",
  מסחרי:  "🏢",
  אחר:    "📦",
};

const STATUS_CHIPS = [
  { key: "מושכר",  label: "מושכר",  color: "bg-green-100 text-green-700" },
  { key: "פנוי",   label: "פנוי",   color: "bg-yellow-100 text-yellow-700" },
  { key: "בבנייה", label: "בבנייה", color: "bg-blue-100 text-blue-700" },
];

function fmt(n: number): string {
  if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `₪${Math.round(n / 1_000)}K`;
  return `₪${n.toLocaleString("he-IL")}`;
}

function typeIcon(t: string) {
  return TYPE_ICON[t] ?? "🏘️";
}

function statusColor(s: string) {
  return STATUS_CHIPS.find((c) => c.key === s)?.color ?? "bg-gray-100 text-gray-600";
}

// ── Asset Detail ────────────────────────────────────────────────

function AssetDetail({
  assetId,
  onBack,
}: {
  assetId: string;
  onBack: () => void;
}) {
  const [state, setState] = useState<DetailState>({ status: "loading" });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Local editable state — synced from loaded data
  const [editValue, setEditValue]    = useState("");
  const [editIncome, setEditIncome]  = useState("");
  const [editStatus, setEditStatus]  = useState("");
  const [editNotes, setEditNotes]    = useState("");

  useEffect(() => {
    fetchAsset(assetId)
      .then((data) => {
        setState({ status: "ok", data });
        setEditValue(data.value > 0 ? String(data.value) : "");
        setEditIncome(data.rental_income > 0 ? String(data.rental_income) : "");
        setEditStatus(data.status);
        setEditNotes(data.notes);
      })
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [assetId]);

  function showToast(type: "ok" | "err", text: string) {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast({ type, text });
    timerRef.current = setTimeout(() => setToast(null), 2500);
  }

  async function handleSave() {
    if (state.status !== "ok" || saving) return;
    setSaving(true);
    try {
      const fields: Record<string, string | number> = {};
      const v = parseFloat(editValue);
      const i = parseFloat(editIncome);
      if (!isNaN(v) && v !== state.data.value)        fields["שווי נוכחי"]    = v;
      if (!isNaN(i) && i !== state.data.rental_income) fields["הכנסה חודשית"] = i;
      if (editStatus && editStatus !== state.data.status) fields["סטטוס"] = editStatus;
      if (editNotes !== state.data.notes)               fields["הערות"]  = editNotes;

      if (Object.keys(fields).length === 0) {
        showToast("ok", "אין שינויים לשמור");
        return;
      }
      await updateAsset(assetId, fields as Parameters<typeof updateAsset>[1]);
      setState((prev) =>
        prev.status === "ok"
          ? {
              status: "ok",
              data: {
                ...prev.data,
                value:         !isNaN(v) ? v : prev.data.value,
                rental_income: !isNaN(i) ? i : prev.data.rental_income,
                equity:        (!isNaN(v) ? v : prev.data.value) - prev.data.mortgage,
                status:        editStatus || prev.data.status,
                notes:         editNotes,
              },
            }
          : prev,
      );
      showToast("ok", "נשמר ✓");
    } catch {
      showToast("err", "שמירה נכשלה");
    } finally {
      setSaving(false);
    }
  }

  const d = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-32">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none">←</button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-black text-gray-900 truncate">
            {d ? `${typeIcon(d.type)} ${d.name}` : "נכס"}
          </h1>
          <p className="text-xs text-gray-400">Asset Card</p>
        </div>
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
        <div className="mx-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {state.message}
        </div>
      )}

      {d && (
        <div className="flex flex-col gap-3 px-4">
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "שווי נוכחי",   value: fmt(d.value),        color: "text-gray-900" },
              { label: "הון עצמי",     value: fmt(d.equity),       color: d.equity >= 0 ? "text-green-600" : "text-red-600" },
              { label: "משכנתא",       value: fmt(d.mortgage),     color: "text-gray-700" },
              { label: "הכנסה/חודש",  value: fmt(d.rental_income), color: "text-blue-600" },
            ].map((k) => (
              <div key={k.label} className="bg-white rounded-xl shadow-sm p-3">
                <p className="text-[11px] text-gray-400 mb-0.5">{k.label}</p>
                <p className={`text-lg font-black ${k.color}`}>{k.value}</p>
              </div>
            ))}
          </div>

          {/* עלות רכישה — read-only */}
          {d.cost > 0 && (
            <div className="bg-white rounded-xl shadow-sm p-4 flex justify-between items-center">
              <p className="text-sm text-gray-500">עלות רכישה</p>
              <p className="text-sm font-semibold text-gray-700">{fmt(d.cost)}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Fixed action bar ── */}
      {d && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 pt-3 pb-4 flex flex-col gap-3 shadow-xl">
          {/* Status chips */}
          <div className="flex gap-2">
            {STATUS_CHIPS.map((chip) => (
              <button
                key={chip.key}
                onClick={() => setEditStatus(chip.key)}
                className={`flex-1 text-xs py-1.5 rounded-full font-medium transition-all
                  ${editStatus === chip.key ? "bg-blue-500 text-white shadow" : `${chip.color}`}`}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Value + income inputs */}
          <div className="flex gap-2">
            <input
              type="number"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              placeholder="שווי נוכחי"
              className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400"
              dir="ltr"
            />
            <input
              type="number"
              value={editIncome}
              onChange={(e) => setEditIncome(e.target.value)}
              placeholder="הכנסה/חודש"
              className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400"
              dir="ltr"
            />
          </div>

          {/* Notes + save */}
          <div className="flex gap-2">
            <input
              type="text"
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
              placeholder="הערות..."
              className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400"
              dir="rtl"
            />
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-blue-500 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70"
            >
              {saving ? "…" : "שמור"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Assets Overview ──────────────────────────────────────────────

export function PersonalMode({ onBack }: Props) {
  const [state, setState] = useState<ListState>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    fetchAssets()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, []);

  if (selectedId) {
    return <AssetDetail assetId={selectedId} onBack={() => setSelectedId(null)} />;
  }

  const d = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none">←</button>
        <div>
          <h1 className="text-lg font-black text-gray-900">Personal Mode</h1>
          <p className="text-xs text-gray-400">
            {d ? `${d.count} נכסים` : "Assets"}
          </p>
        </div>
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {state.status === "error" && (
        <div className="mx-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {state.message}
        </div>
      )}

      {d && (
        <div className="flex flex-col gap-3 px-4">
          {/* Portfolio summary */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-gray-400 mb-3">תיק נכסים</p>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-lg font-black text-gray-900">{fmt(d.total_value)}</p>
                <p className="text-[10px] text-gray-400">שווי כולל</p>
              </div>
              <div>
                <p className={`text-lg font-black ${d.net_equity >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {fmt(d.net_equity)}
                </p>
                <p className="text-[10px] text-gray-400">הון עצמי</p>
              </div>
              <div>
                <p className="text-lg font-black text-blue-600">{fmt(d.monthly_income)}</p>
                <p className="text-[10px] text-gray-400">הכנסה/חודש</p>
              </div>
            </div>
          </div>

          {/* Asset cards */}
          {d.assets.length === 0 ? (
            <p className="text-center text-gray-400 text-sm pt-8">אין נכסים רשומים</p>
          ) : (
            d.assets.map((asset) => (
              <div
                key={asset.id}
                className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-3 active:opacity-70 cursor-pointer"
                onClick={() => setSelectedId(asset.id)}
              >
                <div className="text-3xl flex-shrink-0">{typeIcon(asset.type)}</div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{asset.name || "—"}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    {asset.status && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${statusColor(asset.status)}`}>
                        {asset.status}
                      </span>
                    )}
                    {asset.rental_income > 0 && (
                      <span className="text-[10px] text-blue-500">{fmt(asset.rental_income)}/חודש</span>
                    )}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className={`text-sm font-bold ${asset.equity >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {fmt(asset.equity)}
                  </p>
                  <p className="text-[10px] text-gray-400">הון עצמי</p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
