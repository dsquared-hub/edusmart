import { arr, num, obj, str } from "./util";

const R = 42;

function slicePath(i: number, n: number): string {
  const a0 = (i / n) * Math.PI * 2 - Math.PI / 2;
  const a1 = ((i + 1) / n) * Math.PI * 2 - Math.PI / 2;
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const p = (a: number) => `${50 + R * Math.cos(a)} ${50 + R * Math.sin(a)}`;
  return `M50 50 L${p(a0)} A${R} ${R} 0 ${large} 1 ${p(a1)} Z`;
}

function Pie({ filled, parts }: { filled: number; parts: number }) {
  return (
    <svg viewBox="0 0 100 100" className="h-24 w-24" aria-hidden="true">
      {parts === 1 ? (
        <circle cx="50" cy="50" r={R} fill={filled ? "rgb(var(--primary))" : "rgb(var(--surface))"} />
      ) : (
        Array.from({ length: parts }, (_, i) => (
          <path
            key={i}
            d={slicePath(i, parts)}
            fill={i < filled ? "rgb(var(--primary))" : "rgb(var(--surface))"}
            stroke="rgb(var(--ink))"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        ))
      )}
      <circle cx="50" cy="50" r={R} fill="none" stroke="rgb(var(--ink))" strokeWidth="3" />
    </svg>
  );
}

/** Дроби кружками: 5/4 → один полный кружок и ещё 1/4. */
export function Fractions({ data }: { data: Record<string, unknown> }) {
  const items = arr(data.items, 4).map((it) => {
    const o = obj(it);
    const den = Math.round(num(o.denominator, 0));
    const numer = Math.round(num(o.numerator, 0));
    return { den, numer, label: str(o.label) || `${numer}/${den}` };
  });
  return (
    <div className="flex flex-wrap items-end justify-center gap-5">
      {items.map((it, i) => {
        const valid = it.den >= 1 && it.den <= 12 && it.numer >= 0 && it.numer <= it.den * 3;
        const wholes = valid ? Math.max(1, Math.ceil(it.numer / it.den)) : 0;
        return (
          <figure key={i} className="flex flex-col items-center gap-1" aria-label={`Дробь ${it.label}`}>
            <div className="flex gap-1">
              {Array.from({ length: wholes }, (_, w) => (
                <Pie key={w} parts={it.den} filled={Math.min(it.den, Math.max(0, it.numer - w * it.den))} />
              ))}
            </div>
            <figcaption className="text-2xl font-black">{it.label}</figcaption>
          </figure>
        );
      })}
    </div>
  );
}
