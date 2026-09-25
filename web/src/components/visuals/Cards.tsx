import { arr, obj, str } from "./util";

export function Cards({ data }: { data: Record<string, unknown> }) {
  const items = arr(data.items, 4)
    .map((it) => {
      const o = obj(it);
      return { title: str(o.title), text: str(o.text) || (typeof it === "string" ? it : "") };
    })
    .filter((c) => c.title || c.text);
  if (!items.length) return null;
  return (
    <div className={`grid gap-3 ${items.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
      {items.map((c, i) => (
        <div key={i} className="rounded-2xl bg-surface p-3 border-[length:var(--border-w)] border-line">
          {c.title && <div className="text-lg font-black text-primary">{c.title}</div>}
          {c.text && <div className="font-semibold leading-snug">{c.text}</div>}
        </div>
      ))}
    </div>
  );
}
