import { useEffect, useRef, useState } from "react";
import { fetchVentures, fetchVenture, createVenture, updateVenture } from "../api";
import type { Venture, VenturesResponse } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

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
type StatusTone = "neutral" | "info" | "warning" | "success" | "danger";

const STAGES = [
  "Research", "Supplier/Source Contact", "Due Diligence", "Legal/Tax Review",
  "Smoke Test", "GO", "NO-GO", "Converted",
];

const STAGE_TONE: Record<string, StatusTone> = {
  Research: "neutral",
  "Supplier/Source Contact": "info",
  "Due Diligence": "warning",
  "Legal/Tax Review": "info",
  "Smoke Test": "warning",
  GO: "success",
  "NO-GO": "danger",
  Converted: "success",
};

const CONVICTION_TONE: Record<string, StatusTone> = {
  Low: "neutral",
  Medium: "warning",
  High: "success",
};

const DOMAINS = ["Real Estate", "Import", "SaaS", "Recruitment", "General"];
const CONVICTIONS = ["Low", "Medium", "High"];

function fmt(n: number): string {
  if (!n) return "—";
  if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `₪${Math.round(n / 1_000).toLocaleString("he-IL")}K`;
  return `₪${n.toLocaleString("he-IL")}`;
}

function stageTone(stage: string): StatusTone {
  return STAGE_TONE[stage] ?? "neutral";
}

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
      showToast("ok", "נשמר");
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
    <main className="ventures-screen ventures-screen--detail">
      <div className="ventures-shell">
        <PageHeader
          onBack={onBack}
          eyebrow="Venture card"
          title={d?.name || "Venture"}
          subtitle={d?.domain || "Strategic Layer"}
          badge={d?.stage ? <StatusBadge tone={stageTone(d.stage)}>{d.stage}</StatusBadge> : undefined}
        />

        {toast && (
          <div className={`ventures-toast ${toast.type === "err" ? "ventures-toast--error" : ""}`} role="status">
            {toast.text}
          </div>
        )}

        {state.status === "loading" && <ScreenState state="loading" message="טוען את כרטיס ההזדמנות" />}
        {state.status === "error" && <ScreenState state="error" message={state.message} />}

        {d && (
          <div className="ventures-detail-stack">
            <Surface>
              <p className="ventures-section-label">פרטי החלטה</p>
              <div className="ventures-detail-grid">
                <div>
                  <p className="ventures-detail-label">פוטנציאל משוער</p>
                  <p className="ventures-detail-value">{fmt(d.estimated_potential)}</p>
                </div>
                <div>
                  <p className="ventures-detail-label">ביטחון</p>
                  <StatusBadge tone={CONVICTION_TONE[d.conviction] ?? "neutral"}>{d.conviction || "—"}</StatusBadge>
                </div>
                <div>
                  <p className="ventures-detail-label">תאריך החלטה משוער</p>
                  <p className="ventures-detail-value">{d.target_decision_date || "—"}</p>
                </div>
                <div>
                  <p className="ventures-detail-label">תחום</p>
                  <p className="ventures-detail-value">{d.domain || "—"}</p>
                </div>
              </div>
            </Surface>

            {d.decision_log && (
              <Surface variant="subtle">
                <p className="ventures-section-label">Decision Log</p>
                <p className="ventures-detail-copy">{d.decision_log}</p>
              </Surface>
            )}
          </div>
        )}
      </div>

      {d && (
        <div className="ventures-action-bar">
          <div className="ventures-action-bar__inner">
            <div className="ventures-action-row" aria-label="שלב">
              {STAGES.map((stage) => (
                <button
                  type="button"
                  key={stage}
                  onClick={() => setEditStage(stage)}
                  className="ventures-choice"
                  aria-pressed={editStage === stage}
                >
                  {stage}
                </button>
              ))}
            </div>
            <div className="ventures-action-row ventures-action-row--equal" aria-label="רמת ביטחון">
              {CONVICTIONS.map((conviction) => (
                <button
                  type="button"
                  key={conviction}
                  onClick={() => setEditConviction(conviction)}
                  className="ventures-choice"
                  aria-pressed={editConviction === conviction}
                >
                  {conviction}
                </button>
              ))}
            </div>
            <input
              type="text"
              value={editNextAction}
              onChange={(event) => setEditNextAction(event.target.value)}
              placeholder="הצעד הבא"
              className="boss-input"
            />
            <div className="ventures-action-row">
              <input
                type="text"
                value={editNotes}
                onChange={(event) => setEditNotes(event.target.value)}
                placeholder="הערות"
                className="boss-input"
              />
              <button type="button" onClick={handleSave} disabled={saving} className="boss-button boss-button--primary">
                {saving ? "שומר…" : "שמור"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
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
    <div className="ventures-modal" onClick={onCancel} role="presentation">
      <div className="ventures-modal__panel" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="new-venture-title">
        <h2 id="new-venture-title" className="ventures-modal__title">Venture חדש</h2>
        <div className="ventures-form-stack">
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="שם ההזדמנות"
            className="boss-input"
          />
          <select value={domain} onChange={(event) => setDomain(event.target.value)} className="boss-select" aria-label="תחום">
            {DOMAINS.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          {error && <p className="ventures-form-error" role="alert">{error}</p>}
          <div className="ventures-form-actions">
            <button type="button" onClick={onCancel} className="boss-button boss-button--quiet">ביטול</button>
            <button type="button" onClick={handleCreate} disabled={saving || !name.trim()} className="boss-button boss-button--primary">
              {saving ? "יוצר…" : "צור"}
            </button>
          </div>
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
    <main className="ventures-screen">
      <div className="ventures-shell">
        <PageHeader
          onBack={onBack}
          eyebrow="Strategic Layer"
          title="Ventures"
          subtitle={d ? `${d.count} הזדמנויות במעקב` : "בחינת הזדמנויות מהשערה להחלטה"}
          action={(
            <button type="button" onClick={() => setShowNew(true)} className="boss-button boss-button--primary">
              Venture חדש
            </button>
          )}
        />

        <div className="ventures-filters" aria-label="סינון לפי שלב">
          <button
            type="button"
            onClick={() => { setStageFilter(""); load(); }}
            className="ventures-filter"
            aria-pressed={stageFilter === ""}
          >
            הכל
          </button>
          {STAGES.map((stage) => (
            <button
              type="button"
              key={stage}
              onClick={() => { setStageFilter(stage); load(stage); }}
              className="ventures-filter"
              aria-pressed={stageFilter === stage}
            >
              {stage}
            </button>
          ))}
        </div>

        {state.status === "loading" && <ScreenState state="loading" message="טוען הזדמנויות" />}
        {state.status === "error" && (
          <ScreenState
            state="error"
            message={state.message}
            action={(
              <button type="button" onClick={() => load(stageFilter || undefined)} className="boss-button boss-button--quiet">
                ניסיון נוסף
              </button>
            )}
          />
        )}

        {d && d.ventures.length === 0 && (
          <ScreenState state="empty" title="אין הזדמנויות בשלב הזה" message="אפשר לבחור שלב אחר או ליצור Venture חדש." />
        )}

        {d && d.ventures.length > 0 && (
          <div className="ventures-list">
            {d.ventures.map((venture) => (
              <button type="button" key={venture.id} className="ventures-card" onClick={() => setSelectedId(venture.id)}>
                <div className="ventures-card__heading">
                  <p className="ventures-card__name">{venture.name || "—"}</p>
                  {venture.estimated_potential > 0 && <p className="ventures-card__value">{fmt(venture.estimated_potential)}</p>}
                </div>
                <div className="ventures-card__meta">
                  {venture.domain && <span className="ventures-meta">{venture.domain}</span>}
                  <StatusBadge tone={stageTone(venture.stage)}>{venture.stage}</StatusBadge>
                  {venture.conviction && (
                    <StatusBadge tone={CONVICTION_TONE[venture.conviction] ?? "neutral"}>{venture.conviction}</StatusBadge>
                  )}
                </div>
                {venture.next_action && <p className="ventures-next-action">הצעד הבא: {venture.next_action}</p>}
                {venture.target_decision_date && <p className="ventures-date">תאריך החלטה: {venture.target_decision_date}</p>}
              </button>
            ))}
          </div>
        )}
      </div>

      {showNew && (
        <NewVentureForm
          onCancel={() => setShowNew(false)}
          onCreated={(venture) => { setShowNew(false); setSelectedId(venture.id); }}
        />
      )}
    </main>
  );
}
