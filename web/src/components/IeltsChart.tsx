"use client";

/* График к IELTS Writing Task 1 — рисуем сами из данных задания (bar / line / pie / table).
   Цвета серий различимы и в светлой, и в тёмной теме; подписи — текстом, не только цветом. */
import type { IeltsChartData } from "@/lib/types";

const COLORS = ["rgb(var(--primary))", "rgb(var(--accent))", "rgb(var(--good))", "rgb(var(--bad))"];
const W = 640;
const H = 320;
const PAD = { left: 48, right: 16, top: 16, bottom: 56 };

function fmt(v: number) {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

function Legend({ chart }: { chart: IeltsChartData }) {
  if (chart.series.length < 2) return null;
  return (
    <div className="flex flex-wrap justify-center gap-3 text-sm font-bold">
      {chart.series.map((s, i) => (
        <span key={s.name} className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} aria-hidden="true" />
          {s.name}
        </span>
      ))}
    </div>
  );
}

function Axes({ max }: { max: number }) {
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const plotH = H - PAD.top - PAD.bottom;
  return (
    <g className="text-muted" fill="currentColor" fontSize="12">
      {ticks.map((v) => {
        const y = PAD.top + plotH - (v / max) * plotH;
        return (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="currentColor" strokeOpacity="0.2" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end">{fmt(v)}</text>
          </g>
        );
      })}
    </g>
  );
}

function Bars({ chart }: { chart: IeltsChartData }) {
  const max = Math.max(1, ...chart.series.flatMap((s) => s.values)) * 1.1;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const group = plotW / chart.labels.length;
  const bar = (group * 0.7) / chart.series.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={chart.title}>
      <Axes max={max} />
      {chart.labels.map((label, li) => (
        <g key={label}>
          {chart.series.map((s, si) => {
            const h = (s.values[li] / max) * plotH;
            const x = PAD.left + li * group + group * 0.15 + si * bar;
            return <rect key={s.name} x={x} y={PAD.top + plotH - h} width={bar - 2} height={h} rx="3" fill={COLORS[si % COLORS.length]}><title>{`${s.name}: ${fmt(s.values[li])}`}</title></rect>;
          })}
          <text x={PAD.left + li * group + group / 2} y={H - PAD.bottom + 18} textAnchor="middle" fontSize="12" fill="currentColor">{label}</text>
        </g>
      ))}
    </svg>
  );
}

function Lines({ chart }: { chart: IeltsChartData }) {
  const max = Math.max(1, ...chart.series.flatMap((s) => s.values)) * 1.1;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (chart.labels.length === 1 ? plotW / 2 : (i / (chart.labels.length - 1)) * plotW);
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={chart.title}>
      <Axes max={max} />
      {chart.series.map((s, si) => (
        <g key={s.name}>
          <polyline fill="none" stroke={COLORS[si % COLORS.length]} strokeWidth="3" points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} />
          {s.values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r="4" fill={COLORS[si % COLORS.length]}><title>{`${s.name}, ${chart.labels[i]}: ${fmt(v)}`}</title></circle>)}
        </g>
      ))}
      {chart.labels.map((label, i) => (
        <text key={label} x={x(i)} y={H - PAD.bottom + 18} textAnchor="middle" fontSize="12" fill="currentColor">{label}</text>
      ))}
    </svg>
  );
}

function Pie({ chart }: { chart: IeltsChartData }) {
  const values = chart.series[0].values;
  const total = values.reduce((a, b) => a + b, 0) || 1;
  let angle = -Math.PI / 2;
  const r = 110;
  const cx = 150;
  const cy = 140;
  return (
    <div className="flex flex-wrap items-center justify-center gap-4">
      <svg viewBox="0 0 300 280" className="w-full max-w-xs" role="img" aria-label={chart.title}>
        {values.map((v, i) => {
          const a0 = angle;
          const a1 = (angle += (v / total) * Math.PI * 2);
          const large = a1 - a0 > Math.PI ? 1 : 0;
          const d = `M${cx},${cy} L${cx + r * Math.cos(a0)},${cy + r * Math.sin(a0)} A${r},${r} 0 ${large} 1 ${cx + r * Math.cos(a1)},${cy + r * Math.sin(a1)} Z`;
          return <path key={i} d={d} fill={COLORS[i % COLORS.length]} fillOpacity={1 - Math.floor(i / COLORS.length) * 0.35} stroke="rgb(var(--surface))" strokeWidth="2"><title>{`${chart.labels[i]}: ${fmt(v)}`}</title></path>;
        })}
      </svg>
      <ul className="flex flex-col gap-1 text-sm font-bold">
        {values.map((v, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: COLORS[i % COLORS.length], opacity: 1 - Math.floor(i / COLORS.length) * 0.35 }} aria-hidden="true" />
            {chart.labels[i]} — {fmt(v)}{chart.unit}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Table({ chart }: { chart: IeltsChartData }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="p-2 text-left" />
            {chart.series.map((s) => <th key={s.name} className="p-2 text-right font-black">{s.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {chart.labels.map((label, i) => (
            <tr key={label} className="border-t border-line">
              <th className="p-2 text-left font-extrabold">{label}</th>
              {chart.series.map((s) => <td key={s.name} className="p-2 text-right font-bold">{fmt(s.values[i])}{chart.unit}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function IeltsChart({ chart }: { chart: IeltsChartData }) {
  return (
    <figure className="flex flex-col gap-2 rounded-2xl bg-soft p-3 text-ink">
      {chart.title && <figcaption className="text-center font-black">{chart.title}{chart.unit && chart.type !== "table" ? ` (${chart.unit})` : ""}</figcaption>}
      {chart.type === "bar" && <Bars chart={chart} />}
      {chart.type === "line" && <Lines chart={chart} />}
      {chart.type === "pie" && <Pie chart={chart} />}
      {chart.type === "table" && <Table chart={chart} />}
      {chart.type !== "pie" && <Legend chart={chart} />}
    </figure>
  );
}
