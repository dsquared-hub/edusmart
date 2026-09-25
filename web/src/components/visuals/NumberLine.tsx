import { arr, fmt, num, obj, str } from "./util";

const W = 340;
const PAD = 26;
const Y = 58;

export function NumberLine({ data }: { data: Record<string, unknown> }) {
  let min = num(data.min, 0);
  let max = num(data.max, 10);
  if (max <= min) max = min + 10;
  const marks = arr(data.marks).map((m) => {
    const o = obj(m);
    return { value: num(o.value, NaN), label: str(o.label) };
  }).filter((m) => Number.isFinite(m.value));
  // Метки за пределами диапазона расширяют его, а не пропадают
  for (const m of marks) {
    min = Math.min(min, m.value);
    max = Math.max(max, m.value);
  }
  const x = (v: number) => PAD + ((v - min) / (max - min)) * (W - PAD * 2);

  const range = max - min;
  const integerTicks = Number.isInteger(min) && Number.isInteger(max) && range <= 20;
  const ticks = integerTicks ? Array.from({ length: range + 1 }, (_, i) => min + i) : [min, max];

  const hl = arr(data.highlight, 2).map((v) => num(v, NaN));
  const hasHighlight = hl.length === 2 && hl.every(Number.isFinite);
  const labelled = new Set(marks.map((m) => m.value));

  return (
    <svg viewBox={`0 0 ${W} 100`} className="h-auto w-full" role="img" aria-label="Числовая прямая">
      {hasHighlight && (
        <line
          x1={x(Math.min(hl[0], hl[1]))}
          x2={x(Math.max(hl[0], hl[1]))}
          y1={Y}
          y2={Y}
          stroke="rgb(var(--accent))"
          strokeWidth="14"
          strokeLinecap="round"
          opacity="0.8"
        />
      )}
      <line x1={PAD - 12} x2={W - PAD + 14} y1={Y} y2={Y} stroke="rgb(var(--ink))" strokeWidth="3" strokeLinecap="round" />
      <path d={`M${W - PAD + 16} ${Y} l-10 -6 v12 z`} fill="rgb(var(--ink))" />
      {ticks.map((v) => (
        <g key={`t${v}`}>
          <line x1={x(v)} x2={x(v)} y1={Y - 7} y2={Y + 7} stroke="rgb(var(--ink))" strokeWidth="2" />
          {!labelled.has(v) && (
            <text x={x(v)} y={Y + 26} textAnchor="middle" fontSize="13" fill="rgb(var(--muted))" fontWeight="700">
              {fmt(v)}
            </text>
          )}
        </g>
      ))}
      {marks.map((m, i) => (
        <g key={`m${i}`}>
          <circle cx={x(m.value)} cy={Y} r="8" fill="rgb(var(--primary))" stroke="rgb(var(--surface))" strokeWidth="3" />
          <text
            x={x(m.value)}
            y={i % 2 ? Y - 18 : Y + 30}
            textAnchor="middle"
            fontSize="16"
            fontWeight="800"
            fill="rgb(var(--ink))"
          >
            {m.label || fmt(m.value)}
          </text>
        </g>
      ))}
    </svg>
  );
}
