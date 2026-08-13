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
] as const;

type VentureStage = (typeof STAGES)[number];

const STAGE_LABEL: Record<VentureStage, string> = {
  Research: "מחקר",
  "Supplier/Source Contact": "יצירת קשר עם ספק / מקור",
  "Due Diligence": "בדיקת נאותות",
  "Legal/Tax Review": "בדיקה משפטית ומיסויית",
  "Smoke Test": "בדיקת היתכנות",
  GO: "מאושר להתקדמות",
  "NO-GO": "לא מתקדם",
  Converted: "הועבר לביצוע",
};

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
  Medium: "neutral",
  High: "success",
};

const DOMAINS = ["Real Estate", "Import", "SaaS", "Recruitment", "General"];
const CONVICTIONS = ["Low", "Medium", "High"];
const CONVICTION_LABEL: Record<string, string> = {
  Low: "נמוכה",
  Medium: "בינונית",
  High: "גבוהה",
};

function fmt(n: number): string {
  if (!n) return "—";
  if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `₪${Math.round(n / 1_000).toLocaleString("he-IL")}K`;
  return `₪${n.toLocaleString("he-IL")}`;
}

function stageTone(stage: string): StatusTone {
  return STAGE_TONE[stage] ?? "neutral";
}

function isVentureStage(stage: string): stage is VentureStage {
  return STAGES.some((item) => item === stage);
}

function stageLabel(stage: string): string {
  return isVentureStage(stage) ? STAGE_LABEL[stage] : stage;
}

function LifecycleRail({
  selectedStage,
  onSelect,
  includeAll = false,
  counts,
}: {
  selectedStage: string;
  onSelect: (stage: string) => void;
  includeAll?: boolean;
  counts?: Partial<Record<VentureStage, number>>;
}) {
  return (
    <div className="ventures-lifecycle" aria-label="שלבי הזדמנות">
      {includeAll && (
        <button
          type="button"
          onClick={(event) => {
            onSelect("");
            event.currentTarget.scrollIntoView({ block: "nearest", inline: "center" });
          }}
          className="ventures-lifecycle__stage ventures-lifecycle__stage--all boss-bubble--selectable"
          aria-pressed={selectedStage === ""}
        >
          <span className="ventures-lifecycle__index">כל</span>
          <span className="ventures-lifecycle__label">כל השלבים</span>
        </button>
      )}
      {STAGES.map((stage, index) => (
        <button
          type="button"
          key={stage}
          onClick={(event) => {
            onSelect(stage);
            event.currentTarget.scrollIntoView({ block: "nearest", inline: "center" });
          }}
          className="ventures-lifecycle__stage boss-bubble--selectable"
          aria-pressed={selectedStage === stage}
        >
          <span className="ventures-lifecycle__index">{index + 1}</span>
          <span className="ventures-lifecycle__label">{STAGE_LABEL[stage]}</span>
          {counts?.[stage] !== undefined && (
            <span className="ventures-lifecycle__count" aria-label={`${counts[stage]} הזדמנויות`}>
              {counts[stage]}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function WorkspaceHeading({
  eyebrow,
  title,
  context,
  titleId,
}: {
  eyebrow: string;
  title: string;
  context?: string;
  titleId?: string;
}) {
  return (
    <div className="ventures-workspace-heading">
      <div>
        <p className="ventures-workspace-eyebrow">{eyebrow}</p>
        <h2 id={titleId} className="ventures-workspace-title">{title}</h2>
      </div>
      {context && <p className="ventures-workspace-context">{context}</p>}
    </div>
  );
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
    <main className="ventures-screen">
      <div className="ventures-shell ventures-shell--workspace">
        <PageHeader
          onBack={onBack}
          backLabel="לכל ההזדמנויות"
          eyebrow="מרחב עבודה אסטרטגי"
          title={d?.name || "הזדמנות"}
          subtitle={d ? `${d.domain || "ללא תחום"} · מרחב החלטה` : "טוען מרחב החלטה"}
          badge={d?.stage ? <StatusBadge tone={stageTone(d.stage)}>{stageLabel(d.stage)}</StatusBadge> : undefined}
        />

        {toast && (
          <div className={`ventures-toast ${toast.type === "err" ? "ventures-toast--error" : ""}`} role="status">
            {toast.text}
          </div>
        )}

        {state.status === "loading" && <ScreenState state="loading" message="טוען את כרטיס ההזדמנות" />}
        {state.status === "error" && <ScreenState state="error" message={state.message} />}

        {d && (
          <div className="ventures-detail-workspace">
            <div className="ventures-detail-main">
              <Surface className="boss-bubble--information">
                <WorkspaceHeading
                  eyebrow="הקשר"
                  title="תמונת מצב"
                  context="הנתונים הקיימים של ההזדמנות"
                />
                <div className="ventures-detail-grid">
                  <div>
                    <p className="ventures-detail-label">פוטנציאל משוער</p>
                    <p className="ventures-detail-value ventures-detail-value--large">{fmt(d.estimated_potential)}</p>
                  </div>
                  <div>
                    <p className="ventures-detail-label">ביטחון</p>
                    <StatusBadge tone={CONVICTION_TONE[d.conviction] ?? "neutral"}>{CONVICTION_LABEL[d.conviction] || d.conviction || "—"}</StatusBadge>
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

              <Surface variant="subtle" className="boss-bubble--information">
                <WorkspaceHeading
                  eyebrow="הקשר החלטה"
                  title="החלטה וצעד הבא"
                />
                <div className="ventures-decision-context">
                  <div>
                    <p className="ventures-detail-label">הצעד הבא</p>
                    <p className="ventures-detail-copy">{d.next_action || "לא הוגדר צעד הבא"}</p>
                  </div>
                  {d.decision_log && (
                    <div>
                      <p className="ventures-detail-label">יומן החלטות</p>
                      <p className="ventures-detail-copy">{d.decision_log}</p>
                    </div>
                  )}
                  {d.notes && (
                    <div>
                      <p className="ventures-detail-label">הערות</p>
                      <p className="ventures-detail-copy">{d.notes}</p>
                    </div>
                  )}
                </div>
              </Surface>
            </div>

            <Surface variant="raised" className="ventures-editor">
              <WorkspaceHeading
                eyebrow="מסלול התקדמות"
                title="עדכון הזדמנות"
                context="השינויים נשמרים יחד"
              />

              <div className="ventures-editor__section">
                <p className="ventures-field-label">שלב</p>
                <LifecycleRail selectedStage={editStage} onSelect={setEditStage} />
              </div>

              <div className="ventures-editor__section">
                <p className="ventures-field-label">רמת ביטחון</p>
                <div className="ventures-action-row ventures-action-row--equal" aria-label="רמת ביטחון">
                  {CONVICTIONS.map((conviction) => (
                    <button
                      type="button"
                      key={conviction}
                      onClick={() => setEditConviction(conviction)}
                      className="ventures-choice boss-bubble--selectable"
                      aria-pressed={editConviction === conviction}
                    >
                      {CONVICTION_LABEL[conviction]}
                    </button>
                  ))}
                </div>
              </div>

              <label className="ventures-field">
                <span className="ventures-field-label">הצעד הבא</span>
                <input
                  type="text"
                  value={editNextAction}
                  onChange={(event) => setEditNextAction(event.target.value)}
                  placeholder="הצעד הבא"
                  className="boss-input"
                />
              </label>

              <label className="ventures-field">
                <span className="ventures-field-label">הערות</span>
                <input
                  type="text"
                  value={editNotes}
                  onChange={(event) => setEditNotes(event.target.value)}
                  placeholder="הערות"
                  className="boss-input"
                />
              </label>

              <button type="button" onClick={handleSave} disabled={saving} className="boss-button boss-button--primary boss-bubble--action ventures-editor__save">
                {saving ? "שומר…" : "שמור שינויים"}
              </button>
            </Surface>
          </div>
        )}
      </div>
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
        <h2 id="new-venture-title" className="ventures-modal__title">הזדמנות חדשה</h2>
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
            <button type="button" onClick={onCancel} className="boss-button boss-button--quiet boss-bubble--action">ביטול</button>
            <button type="button" onClick={handleCreate} disabled={saving || !name.trim()} className="boss-button boss-button--primary boss-bubble--action">
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
  const totalPotential = d?.ventures.reduce((sum, venture) => sum + (venture.estimated_potential || 0), 0) ?? 0;
  const venturesWithNextAction = d?.ventures.filter((venture) => Boolean(venture.next_action)).length ?? 0;
  const currentViewLabel = stageFilter ? stageLabel(stageFilter) : "כל השלבים";
  const stageCounts = d && !stageFilter
    ? STAGES.reduce<Partial<Record<VentureStage, number>>>((counts, stage) => {
        counts[stage] = d.ventures.filter((venture) => venture.stage === stage).length;
        return counts;
      }, {})
    : undefined;
  const ventureGroups = d
    ? [
        ...STAGES.map((stage, index) => ({
          key: stage,
          stage,
          index: index + 1,
          ventures: d.ventures.filter((venture) => venture.stage === stage),
        })).filter((group) => group.ventures.length > 0),
        {
          key: "uncategorized",
          stage: null,
          index: null,
          ventures: d.ventures.filter((venture) => !isVentureStage(venture.stage)),
        },
      ].filter((group) => group.ventures.length > 0)
    : [];

  return (
    <main className="ventures-screen">
      <div className="ventures-shell ventures-shell--workspace">
        <PageHeader
          onBack={onBack}
          eyebrow="מרחב עבודה אסטרטגי"
          title="הזדמנויות עסקיות"
          subtitle="מרחב עבודה לבחינת הזדמנויות מהשערה להחלטה"
          badge={d ? <StatusBadge tone="info">{d.count} בתצוגה</StatusBadge> : undefined}
          action={(
            <button type="button" onClick={() => setShowNew(true)} className="boss-button boss-button--primary boss-bubble--action">
              הזדמנות חדשה
            </button>
          )}
        />

        {d && (
          <section className="ventures-summary" aria-label="סיכום תצוגה">
            <Surface variant="subtle" padding="compact" className="ventures-summary__item boss-bubble--information">
              <p className="ventures-summary__label">הזדמנויות בתצוגה</p>
              <p className="ventures-summary__value">{d.count}</p>
            </Surface>
            <Surface variant="subtle" padding="compact" className="ventures-summary__item boss-bubble--information">
              <p className="ventures-summary__label">פוטנציאל בתצוגה</p>
              <p className="ventures-summary__value">{fmt(totalPotential)}</p>
            </Surface>
            <Surface variant="subtle" padding="compact" className="ventures-summary__item boss-bubble--information">
              <p className="ventures-summary__label">עם צעד הבא</p>
              <p className="ventures-summary__value">{venturesWithNextAction}</p>
            </Surface>
          </section>
        )}

        <Surface variant="subtle" className="ventures-lifecycle-panel">
          <WorkspaceHeading
            eyebrow="מסלול התקדמות"
            title="מסלול התקדמות"
            context={`תצוגה נוכחית: ${currentViewLabel}`}
          />
          <LifecycleRail
            includeAll
            selectedStage={stageFilter}
            counts={stageCounts}
            onSelect={(stage) => { setStageFilter(stage); load(stage || undefined); }}
          />
        </Surface>

        <section className="ventures-work-area" aria-labelledby="ventures-collection-title">
          <WorkspaceHeading
            eyebrow="הזדמנויות"
            title="הזדמנויות"
            context={d ? `${d.count} פריטים · ${currentViewLabel}` : currentViewLabel}
            titleId="ventures-collection-title"
          />

          {stageFilter && state.status !== "loading" && (
            <div className="ventures-filter-context">
              <div>
                <span className="ventures-filter-context__label">מסנן פעיל</span>
                <strong>{stageFilter}</strong>
              </div>
              <button
                type="button"
                className="boss-button boss-button--quiet boss-bubble--action ventures-filter-context__reset"
                onClick={() => { setStageFilter(""); load(); }}
              >
                הצגת כל השלבים
              </button>
            </div>
          )}

          {state.status === "loading" && <ScreenState state="loading" message="טוען הזדמנויות" />}
          {state.status === "error" && (
            <ScreenState
              state="error"
              message={state.message}
              action={(
                <button type="button" onClick={() => load(stageFilter || undefined)} className="boss-button boss-button--quiet boss-bubble--action">
                  ניסיון נוסף
                </button>
              )}
            />
          )}

          {d && d.ventures.length === 0 && (
            <ScreenState
              state="empty"
              title={stageFilter ? "אין הזדמנויות בשלב הזה" : "אין עדיין הזדמנויות"}
              message={stageFilter ? "אפשר לאפס את המסנן ולחזור לכל השלבים." : "אפשר ליצור הזדמנות ראשונה כדי להתחיל לבחון אותה."}
              action={stageFilter ? (
                <button type="button" onClick={() => { setStageFilter(""); load(); }} className="boss-button boss-button--quiet boss-bubble--action">
                  הצגת כל השלבים
                </button>
              ) : undefined}
            />
          )}

          {d && d.ventures.length > 0 && (
            <div className="ventures-stage-groups">
              {ventureGroups.map((group) => (
                <section className="ventures-stage-group" key={group.key} aria-labelledby={`ventures-stage-${group.index ?? "uncategorized"}`}>
                  <div className="ventures-stage-group__header">
                    <div className="ventures-stage-group__identity">
                      {group.index && <span className="ventures-stage-group__index" aria-hidden="true">{group.index}</span>}
                      <div>
                        <p className="ventures-stage-group__eyebrow">{group.stage ? "שלב נוכחי" : "בדיקת נתונים"}</p>
                        <h3 id={`ventures-stage-${group.index ?? "uncategorized"}`} className="ventures-stage-group__title">
                          {group.stage ? stageLabel(group.stage) : "ללא שלב קנוני"}
                        </h3>
                      </div>
                    </div>
                    <span className="ventures-stage-group__count">{group.ventures.length}</span>
                  </div>

                  <Surface padding="none" className="ventures-collection">
                    <div className="ventures-list">
                      {group.ventures.map((venture) => (
                        <button type="button" key={venture.id} className="ventures-card boss-bubble--action" onClick={() => setSelectedId(venture.id)}>
                          <div className="ventures-card__body">
                            <div className="ventures-card__heading">
                              <p className="ventures-card__name">{venture.name || "—"}</p>
                              <StatusBadge tone={stageTone(venture.stage)}>
                                {isVentureStage(venture.stage) ? stageLabel(venture.stage) : "שלב לא מוכר"}
                              </StatusBadge>
                            </div>

                            {venture.next_action && (
                              <div className="ventures-next-action">
                                <span className="ventures-next-action__label">הצעד הבא</span>
                                <span className="ventures-next-action__text">{venture.next_action}</span>
                              </div>
                            )}

                            <div className="ventures-card__meta">
                              {venture.domain && <span className="ventures-meta">{venture.domain}</span>}
                              {venture.conviction && (
                                <StatusBadge tone={CONVICTION_TONE[venture.conviction] ?? "neutral"}>{CONVICTION_LABEL[venture.conviction] || venture.conviction}</StatusBadge>
                              )}
                              {venture.estimated_potential > 0 && <span className="ventures-card__value">{fmt(venture.estimated_potential)}</span>}
                            </div>
                          </div>
                          <div className="ventures-card__aside">
                            <p className="ventures-card__aside-label">החלטה משוערת</p>
                            <p className="ventures-card__aside-value">{venture.target_decision_date || "—"}</p>
                            <span className="ventures-card__open">פתיחת הזדמנות</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </Surface>
                </section>
              ))}
            </div>
          )}
        </section>
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
