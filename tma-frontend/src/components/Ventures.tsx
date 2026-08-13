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

type StatusTone = "neutral" | "info" | "warning" | "success" | "danger";
type SaveResult = "saved" | "error" | null;

const STAGES = [
  "Research", "Supplier/Source Contact", "Due Diligence", "Legal/Tax Review",
  "Smoke Test", "GO", "NO-GO", "Converted",
] as const;

type VentureStage = (typeof STAGES)[number];

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

function isVentureStage(stage: string): stage is VentureStage {
  return STAGES.some((item) => item === stage);
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
  const selectedRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [selectedStage]);

  return (
    <div className="ventures-lifecycle" aria-label="שלבי Venture">
      {includeAll && (
        <button
          type="button"
          ref={selectedStage === "" ? selectedRef : undefined}
          onClick={(event) => {
            onSelect("");
            event.currentTarget.scrollIntoView({ block: "nearest", inline: "center" });
          }}
          className="ventures-lifecycle__stage ventures-lifecycle__stage--all"
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
          ref={selectedStage === stage ? selectedRef : undefined}
          onClick={(event) => {
            onSelect(stage);
            event.currentTarget.scrollIntoView({ block: "nearest", inline: "center" });
          }}
          className="ventures-lifecycle__stage"
          aria-pressed={selectedStage === stage}
        >
          <span className="ventures-lifecycle__index">{index + 1}</span>
          <span className="ventures-lifecycle__label">{stage}</span>
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
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<SaveResult>(null);

  const [editStage, setEditStage] = useState("");
  const [editConviction, setEditConviction] = useState("");
  const [editNextAction, setEditNextAction] = useState("");
  const [editNotes, setEditNotes] = useState("");

  function loadDetail() {
    setState({ status: "loading" });
    fetchVenture(ventureId)
      .then((data) => {
        setState({ status: "ok", data });
        setEditStage(data.stage);
        setEditConviction(data.conviction);
        setEditNextAction(data.next_action);
        setEditNotes(data.notes);
      })
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }

  useEffect(() => {
    loadDetail();
  }, [ventureId]);

  function resetDraft(data: Venture) {
    setEditStage(data.stage);
    setEditConviction(data.conviction);
    setEditNextAction(data.next_action);
    setEditNotes(data.notes);
  }

  function openEditor() {
    if (state.status !== "ok") return;
    resetDraft(state.data);
    setSaveResult(null);
    setIsEditing(true);
  }

  function closeEditor() {
    if (state.status === "ok") resetDraft(state.data);
    setSaveResult(null);
    setIsEditing(false);
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

      if (Object.keys(fields).length === 0) return;
      await updateVenture(ventureId, fields);
      const updated = await fetchVenture(ventureId);
      setState({ status: "ok", data: updated });
      resetDraft(updated);
      setSaveResult("saved");
    } catch {
      setSaveResult("error");
    } finally {
      setSaving(false);
    }
  }

  const d = state.status === "ok" ? state.data : null;
  const hasChanges = d
    ? editStage !== d.stage
      || editConviction !== d.conviction
      || editNextAction !== d.next_action
      || editNotes !== d.notes
    : false;

  function markDraftChanged() {
    setSaveResult(null);
  }

  return (
    <main className="ventures-screen">
      <div className="ventures-shell ventures-shell--workspace">
        <PageHeader
          onBack={onBack}
          backLabel="לכל ה־Ventures"
          eyebrow="Venture workspace"
          title={d?.name || "Venture"}
          subtitle={d ? `${d.domain || "ללא תחום"} · מרחב החלטה` : "טוען מרחב החלטה"}
          badge={d?.stage ? <StatusBadge tone={stageTone(d.stage)}>{d.stage}</StatusBadge> : undefined}
          action={d && !isEditing ? (
            <button type="button" onClick={openEditor} className="boss-button boss-button--primary">
              עריכת פרטים
            </button>
          ) : undefined}
        />

        {state.status === "loading" && <ScreenState state="loading" message="טוען את כרטיס ההזדמנות" />}
        {state.status === "error" && (
          <ScreenState
            state="error"
            message="לא הצלחנו לטעון את פרטי ההזדמנות. אפשר לנסות שוב."
            action={(
              <button type="button" onClick={loadDetail} className="boss-button boss-button--quiet">
                ניסיון נוסף
              </button>
            )}
          />
        )}

        {d && (
          <div className={`ventures-detail-workspace${isEditing ? " ventures-detail-workspace--editing" : ""}`}>
            <div className="ventures-detail-main">
              <Surface className="ventures-decision-summary">
                <WorkspaceHeading
                  eyebrow="Decision summary"
                  title="תמונת החלטה"
                  context="העובדות המרכזיות הזמינות כרגע"
                />
                <div className="ventures-detail-grid">
                  <div>
                    <p className="ventures-detail-label">שלב נוכחי</p>
                    <StatusBadge tone={stageTone(d.stage)}>{d.stage || "—"}</StatusBadge>
                  </div>
                  <div>
                    <p className="ventures-detail-label">רמת ביטחון</p>
                    <StatusBadge tone={CONVICTION_TONE[d.conviction] ?? "neutral"}>{d.conviction || "—"}</StatusBadge>
                  </div>
                  <div>
                    <p className="ventures-detail-label">פוטנציאל משוער</p>
                    <p className="ventures-detail-value ventures-detail-value--large">{fmt(d.estimated_potential)}</p>
                  </div>
                  <div>
                    <p className="ventures-detail-label">תאריך החלטה משוער</p>
                    <p className="ventures-detail-value">{d.target_decision_date || "—"}</p>
                  </div>
                </div>
              </Surface>

              <Surface variant="subtle" className="ventures-next-action-detail">
                <WorkspaceHeading
                  eyebrow="Next action"
                  title="הצעד הבא"
                />
                <p className={`ventures-detail-copy ventures-next-action-detail__copy${d.next_action ? "" : " ventures-detail-copy--empty"}`}>
                  {d.next_action || "לא הוגדר צעד הבא"}
                </p>
              </Surface>

              <div className="ventures-detail-text-grid">
                <Surface>
                  <WorkspaceHeading eyebrow="Decision log" title="יומן החלטה" />
                  <p className={`ventures-detail-copy${d.decision_log ? "" : " ventures-detail-copy--empty"}`}>
                    {d.decision_log || "אין עדיין טקסט ביומן ההחלטה."}
                  </p>
                </Surface>

                <Surface>
                  <WorkspaceHeading eyebrow="Notes" title="הערות" />
                  <p className={`ventures-detail-copy${d.notes ? "" : " ventures-detail-copy--empty"}`}>
                    {d.notes || "אין הערות נוספות."}
                  </p>
                </Surface>
              </div>

              <Surface variant="subtle" className="ventures-context-facts">
                <WorkspaceHeading eyebrow="Context" title="הקשר" />
                <dl className="ventures-context-facts__list">
                  <div>
                    <dt>תחום</dt>
                    <dd>{d.domain || "—"}</dd>
                  </div>
                  <div>
                    <dt>נוצר בתאריך</dt>
                    <dd>{d.created_at || "—"}</dd>
                  </div>
                </dl>
              </Surface>
            </div>

            {isEditing && (
              <Surface variant="raised" className="ventures-editor" aria-labelledby="venture-edit-title">
                <div className="ventures-editor__header">
                  <WorkspaceHeading
                    eyebrow="Edit mode"
                    title="עדכון Venture"
                    context="רק השדות הנתמכים כיום"
                    titleId="venture-edit-title"
                  />
                  <button type="button" onClick={closeEditor} disabled={saving} className="boss-button boss-button--quiet">
                    ביטול
                  </button>
                </div>

                <div className="ventures-editor__section">
                  <p className="ventures-field-label">שלב</p>
                  <LifecycleRail
                    selectedStage={editStage}
                    onSelect={(stage) => { setEditStage(stage); markDraftChanged(); }}
                  />
                </div>

                <div className="ventures-editor__section">
                  <p className="ventures-field-label">רמת ביטחון</p>
                  <div className="ventures-action-row ventures-action-row--equal" aria-label="רמת ביטחון">
                    {CONVICTIONS.map((conviction) => (
                      <button
                        type="button"
                        key={conviction}
                        onClick={() => { setEditConviction(conviction); markDraftChanged(); }}
                        className="ventures-choice"
                        aria-pressed={editConviction === conviction}
                      >
                        {conviction}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="ventures-field">
                  <span className="ventures-field-label">הצעד הבא</span>
                  <textarea
                    value={editNextAction}
                    onChange={(event) => { setEditNextAction(event.target.value); markDraftChanged(); }}
                    placeholder="הצעד הבא"
                    className="boss-input ventures-textarea ventures-textarea--action"
                  />
                </label>

                <label className="ventures-field">
                  <span className="ventures-field-label">הערות</span>
                  <textarea
                    value={editNotes}
                    onChange={(event) => { setEditNotes(event.target.value); markDraftChanged(); }}
                    placeholder="הערות"
                    className="boss-input ventures-textarea"
                  />
                </label>

                <div
                  className={`ventures-save-state${saveResult === "error" ? " ventures-save-state--error" : ""}`}
                  role={saveResult === "error" ? "alert" : "status"}
                  aria-live="polite"
                >
                  {saving && "שומר את השינויים…"}
                  {!saving && saveResult === "saved" && "נשמר. פרטי ההזדמנות נטענו מחדש."}
                  {!saving && saveResult === "error" && "השמירה נכשלה. השינויים נשארו בטופס ואפשר לנסות שוב."}
                  {!saving && !saveResult && hasChanges && "יש שינויים שעדיין לא נשמרו."}
                  {!saving && !saveResult && !hasChanges && "עדיין לא בוצעו שינויים."}
                </div>

                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving || !hasChanges}
                  className="boss-button boss-button--primary ventures-editor__save"
                >
                  {saving ? "שומר…" : "שמור שינויים"}
                </button>
              </Surface>
            )}
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
  const totalPotential = d?.ventures.reduce((sum, venture) => sum + (venture.estimated_potential || 0), 0) ?? 0;
  const venturesWithNextAction = d?.ventures.filter((venture) => Boolean(venture.next_action)).length ?? 0;
  const currentViewLabel = stageFilter || "כל השלבים";
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
          eyebrow="Strategic workspace"
          title="Ventures"
          subtitle="מרחב עבודה לבחינת הזדמנויות מהשערה להחלטה"
          badge={d ? <StatusBadge tone="info">{d.count} בתצוגה</StatusBadge> : undefined}
          action={(
            <button type="button" onClick={() => setShowNew(true)} className="boss-button boss-button--primary">
              Venture חדש
            </button>
          )}
        />

        {d && (
          <section className="ventures-summary" aria-label="סיכום תצוגה">
            <Surface variant="subtle" padding="compact" className="ventures-summary__item">
              <p className="ventures-summary__label">הזדמנויות בתצוגה</p>
              <p className="ventures-summary__value">{d.count}</p>
            </Surface>
            <Surface variant="subtle" padding="compact" className="ventures-summary__item">
              <p className="ventures-summary__label">פוטנציאל בתצוגה</p>
              <p className="ventures-summary__value">{fmt(totalPotential)}</p>
            </Surface>
            <Surface variant="subtle" padding="compact" className="ventures-summary__item">
              <p className="ventures-summary__label">עם צעד הבא</p>
              <p className="ventures-summary__value">{venturesWithNextAction}</p>
            </Surface>
          </section>
        )}

        <Surface variant="subtle" className="ventures-lifecycle-panel">
          <WorkspaceHeading
            eyebrow="Lifecycle"
            title="מסלול ההזדמנות"
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
            eyebrow="Collection"
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
                className="boss-button boss-button--quiet ventures-filter-context__reset"
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
                <button type="button" onClick={() => load(stageFilter || undefined)} className="boss-button boss-button--quiet">
                  ניסיון נוסף
                </button>
              )}
            />
          )}

          {d && d.ventures.length === 0 && (
            <ScreenState
              state="empty"
              title={stageFilter ? "אין הזדמנויות בשלב הזה" : "אין עדיין הזדמנויות"}
              message={stageFilter ? "אפשר לאפס את המסנן ולחזור לכל השלבים." : "אפשר ליצור Venture ראשון כדי להתחיל לבחון הזדמנות."}
              action={stageFilter ? (
                <button type="button" onClick={() => { setStageFilter(""); load(); }} className="boss-button boss-button--quiet">
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
                        <p className="ventures-stage-group__eyebrow">{group.stage ? "Lifecycle stage" : "Data check"}</p>
                        <h3 id={`ventures-stage-${group.index ?? "uncategorized"}`} className="ventures-stage-group__title">
                          {group.stage || "ללא שלב קנוני"}
                        </h3>
                      </div>
                    </div>
                    <span className="ventures-stage-group__count">{group.ventures.length}</span>
                  </div>

                  <Surface padding="none" className="ventures-collection">
                    <div className="ventures-list">
                      {group.ventures.map((venture) => (
                        <button type="button" key={venture.id} className="ventures-card" onClick={() => setSelectedId(venture.id)}>
                          <div className="ventures-card__body">
                            <div className="ventures-card__heading">
                              <p className="ventures-card__name">{venture.name || "—"}</p>
                              <StatusBadge tone={stageTone(venture.stage)}>
                                {isVentureStage(venture.stage) ? venture.stage : "שלב לא מוכר"}
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
                                <StatusBadge tone={CONVICTION_TONE[venture.conviction] ?? "neutral"}>{venture.conviction}</StatusBadge>
                              )}
                              {venture.estimated_potential > 0 && <span className="ventures-card__value">{fmt(venture.estimated_potential)}</span>}
                            </div>
                          </div>
                          <div className="ventures-card__aside">
                            <p className="ventures-card__aside-label">החלטה משוערת</p>
                            <p className="ventures-card__aside-value">{venture.target_decision_date || "—"}</p>
                            <span className="ventures-card__open">פתיחת Venture</span>
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
