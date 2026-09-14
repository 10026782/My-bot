import { useEffect, useRef, useState } from "react";
import { fetchAssets, fetchAsset, updateAsset } from "../api";
import type { Asset, AssetsResponse } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

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
type Tone = "neutral" | "danger" | "success" | "info" | "accent";

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
  { key: "מושכר", label: "מושכר" },
  { key: "פנוי", label: "פנוי" },
  { key: "בבנייה", label: "בבנייה" },
] as const;

const STATUS_TONE: Record<string, "success" | "warning" | "info"> = {
  "מושכר": "success",
  "פנוי": "warning",
  "בבנייה": "info",
};

function fmt(n: number): string {
  if (!n && n !== 0) return "—";
  if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `₪${Math.round(n / 1_000).toLocaleString("he-IL")}K`;
  return `₪${n.toLocaleString("he-IL")}`;
}

function typeIcon(t: string) {
  return TYPE_ICON[t] ?? "🏘️";
}

function statusTone(s: string): "success" | "warning" | "info" | "neutral" {
  return STATUS_TONE[s] ?? "neutral";
}

function signTone(n: number): Tone {
  return n >= 0 ? "success" : "danger";
}

function Stat({ label, value, tone = "neutral" }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className="personal-mode-stat">
      <p className={`personal-mode-value personal-mode-value--${tone}`}>{value}</p>
      <p className="personal-mode-stat__label">{label}</p>
    </div>
  );
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

  const load = () => {
    setState({ status: "loading" });
    fetchAsset(assetId)
      .then((data) => {
        setState({ status: "ok", data });
        setEditValue(data.current_value > 0 ? String(data.current_value) : "");
        setEditMortgage(data.mortgage_balance > 0 ? String(data.mortgage_balance) : "");
        setEditIncome(data.monthly_income > 0 ? String(data.monthly_income) : "");
        setEditStatus(data.status);
      })
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  if (state.status === "loading") {
    return (
      <main className="ventures-screen personal-mode-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title="נכס" subtitle="Asset Card" />
          <ScreenState state="loading" title="טוען את פרטי הנכס" message="אוסף את הנתונים העדכניים…" />
        </div>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="ventures-screen personal-mode-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title="נכס" subtitle="Asset Card" />
          <ScreenState
            state="error"
            title="לא הצלחנו לטעון"
            message={state.message}
            action={
              <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>
                נסו שוב
              </button>
            }
          />
        </div>
      </main>
    );
  }

  const d = state.data;

  return (
    <main className="ventures-screen personal-mode-screen">
      {toast && (
        <p className={`ventures-toast${toast.type === "err" ? " ventures-toast--error" : ""}`} role="status">
          {toast.text}
        </p>
      )}

      <div className="ventures-shell" style={{ paddingBottom: 260 }}>
        <PageHeader
          onBack={onBack}
          eyebrow="BOSS"
          title={`${typeIcon(d.type)} ${d.name}`}
          subtitle={d.type || "Asset Card"}
          badge={d.status && <StatusBadge tone={statusTone(d.status)}>{d.status}</StatusBadge>}
        />

        <div className="personal-mode-stack">
          <Surface>
            <p className="personal-mode-hint">Balance Sheet</p>
            <div className="personal-mode-detail-grid">
              <Stat label="שווי נכס" value={fmt(d.current_value)} />
              <Stat label="חוב (משכנתא)" value={fmt(d.mortgage_balance)} tone="danger" />
              <Stat label="Equity (כולל)" value={fmt(d.equity)} tone={signTone(d.equity)} />
              <Stat label={`My Equity (${d.ownership_pct}%)`} value={fmt(d.my_equity)} tone={d.my_equity >= 0 ? "info" : "danger"} />
            </div>
          </Surface>

          <Surface className="personal-mode-income-row">
            <div>
              <p className="personal-mode-hint">הכנסה גולמית / חודש</p>
              <p className="personal-mode-income-value">{fmt(d.monthly_income)}</p>
            </div>
            <p className="personal-mode-income-caption">גולמי בלבד — לא כולל הוצאות, מס, שותפים</p>
          </Surface>
        </div>
      </div>

      <div className="personal-mode-footer">
        <div className="ventures-action-row ventures-action-row--equal">
          {STATUS_CHIPS.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={() => setEditStatus(chip.key)}
              aria-pressed={editStatus === chip.key}
              className="ventures-choice boss-bubble--selectable"
            >
              {chip.label}
            </button>
          ))}
        </div>
        <div className="personal-mode-footer-row">
          <input
            type="number"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            placeholder="שווי נוכחי"
            className="boss-input"
            dir="ltr"
          />
          <input
            type="number"
            value={editMortgage}
            onChange={(e) => setEditMortgage(e.target.value)}
            placeholder="יתרת משכנתא"
            className="boss-input"
            dir="ltr"
          />
        </div>
        <div className="personal-mode-footer-row">
          <input
            type="number"
            value={editIncome}
            onChange={(e) => setEditIncome(e.target.value)}
            placeholder="הכנסה גולמית"
            className="boss-input"
            dir="ltr"
          />
          <button type="button" onClick={handleSave} disabled={saving} className="boss-button boss-button--primary boss-bubble--action">
            {saving ? "…" : "שמור"}
          </button>
        </div>
      </div>
    </main>
  );
}

// ── Assets Overview ──────────────────────────────────────────────

export function PersonalMode({ onBack }: Props) {
  const [state, setState] = useState<ListState>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = () => {
    setState({ status: "loading" });
    fetchAssets()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  };

  useEffect(() => {
    load();
  }, []);

  if (selectedId) {
    return <AssetDetail assetId={selectedId} onBack={() => setSelectedId(null)} />;
  }

  if (state.status === "loading") {
    return (
      <main className="ventures-screen personal-mode-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title="Personal Mode" subtitle="Assets Portfolio" />
          <ScreenState state="loading" title="טוען את תיק הנכסים" message="אוסף את התמונה העדכנית…" />
        </div>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="ventures-screen personal-mode-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title="Personal Mode" subtitle="Assets Portfolio" />
          <ScreenState
            state="error"
            title="לא הצלחנו לטעון"
            message={state.message}
            action={
              <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>
                נסו שוב
              </button>
            }
          />
        </div>
      </main>
    );
  }

  const d = state.data;

  return (
    <main className="ventures-screen personal-mode-screen">
      <div className="ventures-shell">
        <PageHeader onBack={onBack} eyebrow="BOSS" title="Personal Mode" subtitle={`${d.count} נכסים`} />

        <div className="personal-mode-stack">
          <Surface>
            <p className="personal-mode-hint">Balance Sheet — {d.count} נכסים</p>
            <div className="personal-mode-stat-row personal-mode-stat-row--3">
              <Stat label="שווי כולל" value={fmt(d.total_value)} />
              <Stat label="חוב כולל" value={fmt(d.total_debt)} tone="danger" />
              <Stat label="Total Equity" value={fmt(d.total_equity)} tone={signTone(d.total_equity)} />
            </div>
            <div className="personal-mode-divider" />
            <div className="personal-mode-stat-row personal-mode-stat-row--2">
              <Stat label="My Equity" value={fmt(d.my_equity)} tone={d.my_equity >= 0 ? "info" : "danger"} />
              <Stat label="הכנסה גולמית/חודש" value={fmt(d.monthly_income)} tone="accent" />
            </div>
          </Surface>

          {d.assets.length === 0 ? (
            <ScreenState state="empty" title="אין נכסים רשומים" />
          ) : (
            <div className="personal-mode-list">
              {d.assets.map((asset) => (
                <Surface
                  key={asset.id}
                  className="personal-mode-asset-card boss-bubble--selectable"
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedId(asset.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedId(asset.id);
                    }
                  }}
                >
                  <div className="personal-mode-asset-card__top">
                    <span className="personal-mode-asset-card__icon">{typeIcon(asset.type)}</span>
                    <div className="personal-mode-asset-card__body">
                      <div className="personal-mode-asset-card__title-row">
                        <p className="personal-mode-asset-card__name">{asset.name || "—"}</p>
                        <p className="personal-mode-asset-card__value">{fmt(asset.current_value)}</p>
                      </div>
                      <div className="personal-mode-asset-card__meta-row">
                        {asset.type && <span className="personal-mode-hint">{asset.type}</span>}
                        {asset.status && <StatusBadge tone={statusTone(asset.status)}>{asset.status}</StatusBadge>}
                        {asset.ownership_pct < 100 && <span className="personal-mode-hint">{asset.ownership_pct}%</span>}
                      </div>
                      <div className="personal-mode-asset-card__stats-row">
                        <span className="personal-mode-hint">
                          Equity{" "}
                          <span className={`personal-mode-inline-value personal-mode-value--${signTone(asset.equity)}`}>
                            {fmt(asset.equity)}
                          </span>
                        </span>
                        {asset.ownership_pct < 100 && (
                          <span className="personal-mode-hint">
                            My Equity{" "}
                            <span className={`personal-mode-inline-value personal-mode-value--${asset.my_equity >= 0 ? "info" : "danger"}`}>
                              {fmt(asset.my_equity)}
                            </span>
                          </span>
                        )}
                        {asset.monthly_income > 0 && (
                          <span className="personal-mode-hint">
                            הכנסה{" "}
                            <span className="personal-mode-inline-value personal-mode-value--accent">{fmt(asset.monthly_income)}</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Surface>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
