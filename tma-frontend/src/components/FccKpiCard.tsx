import type { FccSavingsRelease } from "../types";
import { savingsFollowUp, savingsReleaseModel } from "../lib/fccPresentation";
import { Surface } from "./ui/Surface";

export function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Surface variant="subtle" padding="compact" className="fcc-kpi">
      <p className="fcc-kpi__value">{value}</p>
      <p className="fcc-kpi__label">{label}</p>
      {hint && <p className="fcc-kpi__hint">{hint}</p>}
    </Surface>
  );
}

/** "מתפנה לחיסכון": numbers come from the server; the buttons only name an intent (the draft is the usual review -> אשר). */
export function SavingsReleaseCard({ release, onStart, disabled }: { release: FccSavingsRelease; onStart: (intent: string) => void; disabled: boolean }) {
  const m = savingsReleaseModel(release);
  return (
    <Surface variant="subtle" padding="compact" className="fcc-kpi fcc-release" aria-label="מתפנה לחיסכון">
      <p className="fcc-kpi__value">{m.headline}</p>
      <p className="fcc-kpi__label">מתפנה לחיסכון החודש</p>
      {m.lines.map((l) => <p key={l} className="fcc-kpi__hint">{l}</p>)}
      <p className="fcc-kpi__hint">{m.destination}</p>
      {m.closing && <p className="fcc-release__closing">{m.closing}</p>}
      {m.gapLine && <p className="fcc-kpi__hint">{m.gapLine}</p>}
      <div className="fcc-quick__choices">
        <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={disabled}
                onClick={() => onStart("savings.deposit")}>{m.depositLabel}</button>
        {m.canExplainGap && (
          <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={disabled}
                  onClick={() => onStart("savings.gap_reason")}>תעד סיבה לפער</button>
        )}
      </div>
    </Surface>
  );
}

/** The question right after an income was booked (only while something is still free). */
export function SavingsFollowUp({ release, onStart, onDismiss, disabled }:
  { release: FccSavingsRelease | null | undefined; onStart: (intent: string) => void; onDismiss: () => void; disabled: boolean }) {
  const q = savingsFollowUp(release);
  if (!q) return null;
  return (
    <Surface variant="subtle" padding="compact" className="fcc-release" role="status">
      <p className="fcc-quick__message">{q.message}</p>
      <div className="fcc-quick__choices">
        <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={disabled}
                onClick={() => { onDismiss(); onStart("savings.deposit"); }}>{q.confirm}</button>
        <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onDismiss}>לא עכשיו</button>
      </div>
    </Surface>
  );
}
