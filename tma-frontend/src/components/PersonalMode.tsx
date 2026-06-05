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
  // Hebrew originals
  "דירה":   "🏠", "קרקע":  "🌿", "מסחרי": "🏢", "אחר":   "📦",
  // English
  "Apartment":  "🏠", "Residential": "🏠",
  "Land":       "🌿",
  "Commercial": "🏢", "Industrial": "🏭", "Office": "🏢",
  "Other":      "📦",
};

const STATUS_CHIPS = [
  { key: "מושכר",  label: "מושכר",  color: "bg-green-100 text-green-700" },
  { key: "פנוי",   label: "פנוי",   color: "bg-yellow-100 text-yellow-700" },
  { key: "בבנייה", label: "בבנייה", color: "bg-blue-100 text-blue-700" },
];

function fmt(n: number): string {
  if (!n && n !== 0) return "—";
  if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `₪${Math.round(n / 1_000).toLocaleString("he-IL")}K`;
  return `₪${n.toLocaleString("he-IL")}`;
}

function typeIcon(t: string) {
  return TYPE_ICON[t] ?? "🏘️";
}

function statusBadge(s: string) {
  return STATUS_CHIPS.find((c) => c.key === s)?.color ?? "bg-gray-100 text-gray-600";
}

// ── Asset Detail ────────────────────────────────────────────────

function AssetDetail({ assetId, onBack }: { assetId: string; onBack: () => void }) {
  const [state, setState] = useState<DetailState>({ status: "loading" });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [editValue,    setEditValue]    = useState("");
  const [editMortgage, setEditMortgage] = useState("");
  const [editIncome,   setEditIncome]   = useState("");
  const [editStatus,   setEditStatus]   = useState("");

  useEffect(() => {
    fetchAsset(assetId)
      .then((data) => {
        setState({ status: "ok", data });
        setEditValue(data.current_value > 0 ? String(data.current_value) : "");
        setEditMortgage(data.mortgage_balance > 0 ? String(data.mortgage_balance) : "");
        setEditIncome(data.monthly_income > 0 ? String(data.monthly_income) : "");
        setEditStatus(data.status);
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
      const d = state.data;
      const fields: Parameters<typeof updateAsset>[1] = {};
      const v = parseFloat(editValue);
      const m = parseFloat(editMortgage);
      const i = parseFloat(editIncome);
      if (!isNaN(v) && v !== d.current_value)    fields["Current Value"]    = v;
      if (!isNaN(m) && m !== d.mortgage_balance) fields["Mortgage Balance"] = m;
      if (!isNaN(i) && i !== d.monthly_income)   fields["Monthly Income"]   = i;
      if (editStatus && editStatus !== d.status) fields["Status"]           = editStatus;

      if (Object.keys(fields).length === 0) { showToast("ok", "אין שינויים"); return; }
      await updateAsset(assetId, fields);
      showToast("ok", "נשמר ✓");
      // Re-fetch to get updated Airtable formula fields (Equity / My Equity)
      const updated = await fetchAsset(assetId);
      setState({ status: "ok", data: updated });
    } catch {
      showToast("err", "שמירה נכשלה");
    } finally {
      setSaving(false);
    }
  }

  const d = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-48">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none">←</button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-black text-gray-900 truncate">
            {d ? `${typeIcon(d.type)} ${d.name}` : "נכס"}
          </h1>
          <p className="text-xs text-gray-400">{d?.type || "Asset Card"}</p>
        </div>
        {d?.status && (
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusBadge(d.status)}`}>
            {d.status}
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
          {/* Balance Sheet grid */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-gray-400 mb-3">Balance Sheet</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              {[
                { label: "שווי נכס",         value: fmt(d.current_value),    color: "text-gray-900" },
                { label: "חוב (משכנתא)",     value: fmt(d.mortgage_balance), color: "text-red-600" },
                { label: "Equity (כולל)",    value: fmt(d.equity),           color: d.equity >= 0 ? "text-green-600" : "text-red-600" },
                { label: `My Equity (${d.ownership_pct}%)`, value: fmt(d.my_equity), color: d.my_equity >= 0 ? "text-blue-600" : "text-red-600" },
              ].map((row) => (
                <div key={row.label}>
                  <p className="text-[10px] text-gray-400">{row.label}</p>
                  <p className={`text-base font-bold ${row.color}`}>{row.value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Monthly Income — gross only, no derivations */}
          <div className="bg-white rounded-xl shadow-sm p-4 flex justify-between items-center">
            <div>
              <p className="text-xs text-gray-400">הכנסה גולמית / חודש</p>
              <p className="text-xl font-black text-blue-600">{fmt(d.monthly_income)}</p>
            </div>
            <p className="text-[10px] text-gray-400 max-w-[120px] text-right leading-tight">
              גולמי בלבד — לא כולל הוצאות, מס, שותפים
            </p>
          </div>
        </div>
      )}

      {/* ── Fixed action bar ── */}
      {d && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 pt-3 pb-4 flex flex-col gap-2.5 shadow-xl">
          {/* Status chips */}
          <div className="flex gap-2">
            {STATUS_CHIPS.map((chip) => (
              <button
                key={chip.key}
                onClick={() => setEditStatus(chip.key)}
                className={`flex-1 text-xs py-1.5 rounded-full font-medium transition-all
                  ${editStatus === chip.key ? "bg-blue-500 text-white shadow" : chip.color}`}
              >
                {chip.label}
              </button>
            ))}
          </div>
          {/* Value + Mortgage */}
          <div className="flex gap-2">
            <input type="number" value={editValue} onChange={(e) => setEditValue(e.target.value)}
              placeholder="שווי נוכחי" className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400" dir="ltr" />
            <input type="number" value={editMortgage} onChange={(e) => setEditMortgage(e.target.value)}
              placeholder="יתרת משכנתא" className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400" dir="ltr" />
          </div>
          {/* Income + Save */}
          <div className="flex gap-2">
            <input type="number" value={editIncome} onChange={(e) => setEditIncome(e.target.value)}
              placeholder="הכנסה גולמית" className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400" dir="ltr" />
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
            {d ? `${d.count} נכסים` : "Assets Portfolio"}
          </p>
        </div>
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
          {/* Portfolio Header KPIs */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-gray-400 mb-3">Balance Sheet — {d.count} נכסים</p>

            {/* Row 1: 3 tiles */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              {[
                { label: "שווי כולל",  value: fmt(d.total_value),  color: "text-gray-900" },
                { label: "חוב כולל",   value: fmt(d.total_debt),   color: "text-red-600" },
                { label: "Total Equity", value: fmt(d.total_equity), color: d.total_equity >= 0 ? "text-green-600" : "text-red-600" },
              ].map((k) => (
                <div key={k.label} className="text-center">
                  <p className={`text-base font-black ${k.color}`}>{k.value}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">{k.label}</p>
                </div>
              ))}
            </div>

            {/* Divider */}
            <div className="border-t border-gray-100 mb-3" />

            {/* Row 2: 2 tiles */}
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "My Equity",  value: fmt(d.my_equity),      color: d.my_equity >= 0 ? "text-blue-600" : "text-red-600" },
                { label: "הכנסה גולמית/חודש", value: fmt(d.monthly_income), color: "text-purple-600" },
              ].map((k) => (
                <div key={k.label} className="text-center">
                  <p className={`text-lg font-black ${k.color}`}>{k.value}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">{k.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Asset cards */}
          {d.assets.length === 0 ? (
            <p className="text-center text-gray-400 text-sm pt-8">אין נכסים רשומים</p>
          ) : (
            d.assets.map((asset) => (
              <div
                key={asset.id}
                className="bg-white rounded-xl shadow-sm p-4 active:opacity-70 cursor-pointer"
                onClick={() => setSelectedId(asset.id)}
              >
                <div className="flex items-start gap-3">
                  <div className="text-2xl flex-shrink-0 mt-0.5">{typeIcon(asset.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-gray-900 truncate">{asset.name || "—"}</p>
                      <p className="text-sm font-bold text-gray-900 flex-shrink-0">{fmt(asset.current_value)}</p>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {asset.type && <span className="text-[10px] text-gray-400">{asset.type}</span>}
                      {asset.status && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${statusBadge(asset.status)}`}>
                          {asset.status}
                        </span>
                      )}
                      {asset.ownership_pct < 100 && (
                        <span className="text-[10px] text-gray-400">{asset.ownership_pct}%</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1.5">
                      <div>
                        <span className="text-[10px] text-gray-400">Equity </span>
                        <span className={`text-xs font-bold ${asset.equity >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {fmt(asset.equity)}
                        </span>
                      </div>
                      {asset.ownership_pct < 100 && (
                        <div>
                          <span className="text-[10px] text-gray-400">My Equity </span>
                          <span className={`text-xs font-bold ${asset.my_equity >= 0 ? "text-blue-600" : "text-red-600"}`}>
                            {fmt(asset.my_equity)}
                          </span>
                        </div>
                      )}
                      {asset.monthly_income > 0 && (
                        <div>
                          <span className="text-[10px] text-gray-400">הכנסה </span>
                          <span className="text-xs font-bold text-purple-600">{fmt(asset.monthly_income)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
