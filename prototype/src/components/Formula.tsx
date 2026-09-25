/* Красивое отображение формул без тяжёлых библиотек: «(a + b) / 2» — настоящей дробью,
   переменные — курсивом, степени — надстрочно. */
import { Fragment, type ReactNode } from "react";

function styleVars(text: string): ReactNode[] {
  // Однобуквенные латинские переменные — курсивом, как в учебнике
  return text.split(/(\b[a-zSh]\b|²|³)/g).map((part, i) =>
    /^[a-zSh]$/.test(part) ? (
      <i key={i} className="font-serif">
        {part}
      </i>
    ) : part === "²" || part === "³" ? (
      <sup key={i} className="text-[0.7em]">
        {part === "²" ? "2" : "3"}
      </sup>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
}

export function Formula({ children, big = false }: { children: string; big?: boolean }) {
  const match = children.match(/^(.*?)\(([^)]+)\) \/ (\d+)(.*)$/);
  return (
    <div
      className={`inline-flex flex-wrap items-center gap-x-1.5 rounded-2xl border border-line bg-bg px-4 py-3 font-semibold text-coffee ${
        big ? "text-2xl" : "text-xl"
      }`}
      style={{ fontFamily: '"Cambria Math", "STIX Two Math", Georgia, serif' }}
    >
      {match ? (
        <>
          <span>{styleVars(match[1])}</span>
          <span className="inline-flex flex-col items-center px-0.5 align-middle leading-tight">
            <span className="px-1">{styleVars(match[2])}</span>
            <span className="h-[2px] w-full rounded bg-coffee" />
            <span>{match[3]}</span>
          </span>
          <span>{styleVars(match[4])}</span>
        </>
      ) : (
        styleVars(children)
      )}
    </div>
  );
}
