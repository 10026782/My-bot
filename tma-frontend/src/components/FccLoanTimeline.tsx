import { useState } from "react";
import type { FccLoans } from "../types";
import { TIMELINE_SCOPES, TIMELINE_TITLE, timelineModel, type TimelineScope } from "../lib/fccLoanTimeline";
import { Surface } from "./ui/Surface";

/** When the payment drops and when the interest share falls — render-only; every number comes from the server. */
export function LoanTimeline({ loans }: { loans: FccLoans }) {
  const [scope, setScope] = useState<TimelineScope>("no_mortgage");
  const m = timelineModel(loans.timeline, scope);
  if (!loans.timeline || (!loans.timeline.no_mortgage && !loans.timeline.all)) return null;
  return (
    <Surface variant="subtle" padding="compact" className="fcc-loans-goal fcc-refi" aria-label={TIMELINE_TITLE}>
      <h3 className="fcc-loans-goal__title">{TIMELINE_TITLE}</h3>
      <div role="group" aria-label="היקף" className="fcc-chips">
        {TIMELINE_SCOPES.map((s) => (
          <button key={s.key} type="button" className={`fcc-chip${scope === s.key ? " fcc-chip--on" : ""}`} aria-pressed={scope === s.key} onClick={() => setScope(s.key)}>{s.label}</button>
        ))}
      </div>
      {!m ? <p className="fcc-loan__meta">אין הלוואות עם נתונים מספיקים בהיקף הזה</p> : (
        <>
          <dl className="fcc-loans-goal__grid">
            {m.summary.map((l) => <div key={l.label}><dt>{l.label}</dt><dd>{l.value}</dd></div>)}
          </dl>
          <h4 className="fcc-pay__subhead">מתי ההחזר החודשי יורד</h4>
          {m.drops.length === 0 ? <p className="fcc-loan__meta">ההחזר לא יורד באופן ניכר עד הסיום</p> : (
            <ul className="fcc-list">{m.drops.map((d) => <li key={d.key}><strong>{d.title}</strong><div className="fcc-loan__meta">{d.detail}</div></li>)}</ul>
          )}
          <h4 className="fcc-pay__subhead">מתי הריבית הופכת לחלק קטן מההחזר</h4>
          {m.thresholds.length === 0 ? <p className="fcc-loan__meta">הריבית לא יורדת מתחת ל-30% מההחזר</p> : (
            <ul className="fcc-list">{m.thresholds.map((t) => <li key={t.key}><strong>{t.title}</strong><div className="fcc-loan__meta">{t.detail}</div></li>)}</ul>
          )}
          <h4 className="fcc-pay__subhead">שנה אחרי שנה</h4>
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="שנה אחרי שנה">
            <table className="fcc-compare__table">
              <thead><tr><th>חודש</th><th>החזר</th><th>ריבית</th><th>חלק הריבית</th></tr></thead>
              <tbody>{m.yearly.map((y) => <tr key={y.key}><th scope="row">{y.month}</th><td>{y.payment}</td><td>{y.interest}</td><td>{y.share}</td></tr>)}</tbody>
            </table>
          </div>
          {m.hint && <p className="fcc-loan__meta">{m.hint}</p>}
          <p className="fcc-loan__meta">{m.note}</p>
        </>
      )}
    </Surface>
  );
}
