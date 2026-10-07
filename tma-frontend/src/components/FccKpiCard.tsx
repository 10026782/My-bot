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
