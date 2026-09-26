"use client";

/* Текст от ИИ с формулами: $…$ и $$…$$ (LaTeX) рисуются KaTeX, остальное — обычный текст.
   Ошибка в формуле не ломает страницу — показываем её исходник. */
import "katex/dist/katex.min.css";
import katex from "katex";
import { Fragment, useMemo } from "react";

const FORMULA = /\$\$([^$]+?)\$\$|\$([^$\n]+?)\$/g;

type Part = { text: string } | { html: string; block: boolean };

function split(source: string): Part[] {
  const parts: Part[] = [];
  let last = 0;
  for (const match of source.matchAll(FORMULA)) {
    const index = match.index ?? 0;
    if (index > last) parts.push({ text: source.slice(last, index) });
    const block = match[1] !== undefined;
    const tex = (match[1] ?? match[2]).trim();
    try {
      parts.push({ html: katex.renderToString(tex, { displayMode: block, throwOnError: true, output: "html" }), block });
    } catch {
      parts.push({ text: match[0] });
    }
    last = index + match[0].length;
  }
  if (last < source.length) parts.push({ text: source.slice(last) });
  return parts;
}

export function MathText({ text }: { text: string }) {
  const parts = useMemo(() => (text.includes("$") ? split(text) : [{ text }]), [text]);
  return (
    <>
      {parts.map((part, i) =>
        "text" in part ? (
          <Fragment key={i}>{part.text}</Fragment>
        ) : (
          // KaTeX сам экранирует содержимое формулы — вставка безопасна
          <span key={i} className={part.block ? "block overflow-x-auto py-1" : "inline-block max-w-full overflow-x-auto align-middle"} dangerouslySetInnerHTML={{ __html: part.html }} />
        ),
      )}
    </>
  );
}
