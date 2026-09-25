import { arr, str } from "./util";

/** Цепочка действий: кружок-номер → стрелка вниз → следующий шаг. */
export function StepArrows({ data }: { data: Record<string, unknown> }) {
  const items = arr(data.items, 5).map(str).filter(Boolean);
  return (
    <ol className="flex flex-col items-stretch">
      {items.map((item, i) => (
        <li key={i} className="flex flex-col items-center">
          <div className="flex w-full items-center gap-3 rounded-2xl bg-surface px-4 py-3 border-[length:var(--border-w)] border-line">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-lg font-black text-on-primary">
              {i + 1}
            </span>
            <span className="text-lg font-bold">{item}</span>
          </div>
          {i < items.length - 1 && (
            <svg viewBox="0 0 24 28" className="h-7 w-6" aria-hidden="true">
              <path d="M12 2 V22 M5 16 L12 24 L19 16" stroke="rgb(var(--primary))" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </li>
      ))}
    </ol>
  );
}
