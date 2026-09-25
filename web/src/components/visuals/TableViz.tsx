import { arr, str } from "./util";

export function TableViz({ data }: { data: Record<string, unknown> }) {
  const headers = arr(data.headers, 5).map(str);
  const rows = arr(data.rows, 6).map((r) => arr(r, 5).map(str));
  if (!headers.length && !rows.length) return null;
  return (
    <div className="overflow-x-auto rounded-2xl border-[length:var(--border-w)] border-line bg-surface">
      <table className="w-full border-collapse text-center text-lg">
        {headers.length > 0 && (
          <thead>
            <tr className="bg-primary text-on-primary">
              {headers.map((h, i) => (
                <th key={i} scope="col" className="px-3 py-2 font-extrabold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className={r % 2 ? "bg-soft/60" : ""}>
              {row.map((cell, c) => (
                <td key={c} className="border-t-2 border-line px-3 py-2 font-bold">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
