import type { BarChartModel, LineChartModel } from "../lib/familyWealth";
import { CHART } from "../lib/familyWealth";

const AXIS = { fill: "currentColor", fillOpacity: 0.7, fontSize: 13 } as const;

function Legend({ items }: { items: { name: string; color: string }[] }) {
  return (
    <div className="pl-legend">
      {items.map((i) => <span key={i.name}><i style={{ background: i.color }} />{i.name}</span>)}
    </div>
  );
}

/** Draws a model the lib already scaled; no financial calculation here. */
export function LineChart({ model, xLabel, title }: { model: LineChartModel; xLabel: string; title: string }) {
  return (
    <div>
      <svg viewBox={`0 0 ${CHART.w} ${CHART.h}`} role="img" aria-label={title} className="pl-chart">
        {model.yTicks.map((t) => (
          <g key={`y${t.label}-${t.pos}`}>
            <line x1={CHART.l} x2={CHART.w - CHART.r} y1={t.pos} y2={t.pos} stroke="currentColor" strokeOpacity={0.12} />
            <text x={CHART.l - 6} y={t.pos + 4} textAnchor="end" {...AXIS}>{t.label}</text>
          </g>
        ))}
        {model.xTicks.map((t) => <text key={`x${t.label}-${t.pos}`} x={t.pos} y={CHART.h - 14} textAnchor="middle" {...AXIS}>{t.label}</text>)}
        <text x={CHART.w / 2} y={CHART.h - 1} textAnchor="middle" {...AXIS}>{xLabel}</text>
        {model.lines.map((l) => (
          <g key={l.name}>
            <polyline points={l.points} fill="none" stroke={l.color} strokeWidth={2} strokeDasharray={l.dash} />
            {l.dots.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={3} fill={l.color} />)}
          </g>
        ))}
      </svg>
      <Legend items={model.lines.map((l) => ({ name: l.name, color: l.color }))} />
    </div>
  );
}

export function BarChart({ model, title }: { model: BarChartModel; title: string }) {
  return (
    <div>
      <svg viewBox={`0 0 ${CHART.w} ${CHART.h}`} role="img" aria-label={title} className="pl-chart">
        {model.yTicks.map((t) => (
          <g key={`y${t.label}-${t.pos}`}>
            <line x1={CHART.l} x2={CHART.w - CHART.r} y1={t.pos} y2={t.pos} stroke="currentColor" strokeOpacity={0.12} />
            <text x={CHART.l - 6} y={t.pos + 4} textAnchor="end" {...AXIS}>{t.label}</text>
          </g>
        ))}
        {model.groups.map((g) => (
          <g key={g.label}>
            {g.bars.map((b, i) => <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} fill={b.color} rx={2} />)}
            <text x={g.x} y={CHART.h - 14} textAnchor="middle" {...AXIS}>{g.label}</text>
          </g>
        ))}
      </svg>
      <Legend items={model.legend} />
    </div>
  );
}

export function StackBar({ parts, formatValue, formatShare }: {
  parts: { name: string; value: number; share: number; color: string }[]; formatValue: (v: number) => string; formatShare: (s: number) => string;
}) {
  return (
    <div>
      <div className="pl-stack" role="img" aria-label="חלוקת התוצאה: הפקדות, רווחים, עלויות">
        {parts.map((p) => <span key={p.name} style={{ inlineSize: `${(Math.max(p.share, 0) * 100).toFixed(2)}%`, background: p.color }} />)}
      </div>
      <dl className="pl-stack__rows">
        {parts.map((p) => (
          <div key={p.name}><dt><i style={{ background: p.color }} />{p.name}</dt><dd>{formatValue(p.value)} ({formatShare(p.share)})</dd></div>
        ))}
      </dl>
    </div>
  );
}
