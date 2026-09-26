"use client";

/* IELTS Writing: задание (с графиком для Task 1), редактор со счётчиком слов и таймером,
   черновик сохраняется сам. После сдачи — Band по 4 критериям, ошибки подсвечены в тексте. */
import { useEffect, useMemo, useRef, useState } from "react";
import { IeltsChart } from "@/components/IeltsChart";
import { Thinking } from "@/components/Thinking";
import { Dots, Notice } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { IeltsAttempt, IeltsWritingResult } from "@/lib/types";

const CRITERIA = ["TR", "CC", "LR", "GRA"] as const;
const ERROR_TONE: Record<string, string> = {
  grammar: "bg-bad/20",
  vocabulary: "bg-accent/30",
  spelling: "bg-primary/20",
  punctuation: "bg-good/25",
  style: "bg-soft",
};

function countWords(text: string) {
  return (text.match(/[A-Za-z0-9’'-]+/g) ?? []).length;
}

function clock(seconds: number) {
  const m = Math.floor(Math.abs(seconds) / 60);
  const s = Math.abs(seconds) % 60;
  return `${seconds < 0 ? "−" : ""}${m}:${String(s).padStart(2, "0")}`;
}

/** Эссе с подсвеченными ошибками: каждая цитата — <mark> с подсказкой. */
function Highlighted({ text, errors }: { text: string; errors: IeltsWritingResult["errors"] }) {
  const parts = useMemo(() => {
    const lower = text.toLowerCase();
    const spans: { start: number; end: number; i: number }[] = [];
    errors.forEach((e, i) => {
      const at = lower.indexOf(e.quote.toLowerCase());
      if (at >= 0 && !spans.some((s) => at < s.end && at + e.quote.length > s.start)) spans.push({ start: at, end: at + e.quote.length, i });
    });
    spans.sort((a, b) => a.start - b.start);
    const out: { text: string; error?: number }[] = [];
    let last = 0;
    for (const s of spans) {
      if (s.start > last) out.push({ text: text.slice(last, s.start) });
      out.push({ text: text.slice(s.start, s.end), error: s.i });
      last = s.end;
    }
    out.push({ text: text.slice(last) });
    return out;
  }, [text, errors]);
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((p, i) =>
        p.error === undefined ? (
          <span key={i}>{p.text}</span>
        ) : (
          <mark key={i} className={`rounded px-0.5 text-ink ${ERROR_TONE[errors[p.error].type] ?? "bg-bad/20"}`} title={`→ ${errors[p.error].fix}`}>
            {p.text}
            <sup className="ml-0.5 text-[0.65rem] font-black">{p.error + 1}</sup>
          </mark>
        ),
      )}
    </p>
  );
}

function Result({ attempt }: { attempt: IeltsAttempt }) {
  const t = useT();
  const r = attempt.result as unknown as IeltsWritingResult;
  const essay = String(attempt.answers.text ?? "");
  return (
    <>
      <section className="card flex flex-col items-center gap-1 text-center anim-pop">
        <span className="text-sm font-extrabold uppercase text-muted">Overall Band</span>
        <span className="text-6xl font-black text-primary">{attempt.band?.toFixed(1)}</span>
        <span className="text-sm font-bold text-muted">{t("ielts.words", { n: r.words, min: r.min_words })}</span>
        {r.under_length && <Notice>{t("ielts.under_length", { min: r.min_words })}</Notice>}
      </section>

      <section className="grid grid-cols-2 gap-2">
        {CRITERIA.map((k) => (
          <div key={k} className="card flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-black">{t(`ielts.criteria.${k}`)}</span>
              <span className="text-2xl font-black">{r.criteria[k].band.toFixed(1)}</span>
            </div>
            <p className="text-xs font-bold text-muted">{r.criteria[k].comment}</p>
          </div>
        ))}
      </section>
      <p className="text-center text-xs font-bold text-muted">
        {t("ielts.two_examiners", {
          a: CRITERIA.map((k) => r.examiners.A[k].toFixed(1)).join(" / "),
          b: CRITERIA.map((k) => r.examiners.B[k].toFixed(1)).join(" / "),
        })}
      </p>

      {r.summary && <Notice>💡 {r.summary}</Notice>}

      <section className="card flex flex-col gap-3">
        <h2 className="text-lg font-black">✍️ {t("ielts.your_essay")}</h2>
        <Highlighted text={essay} errors={r.errors} />
      </section>

      {r.errors.length > 0 && (
        <section className="card flex flex-col gap-2">
          <h2 className="text-lg font-black">🔍 {t("ielts.errors", { n: r.errors.length })}</h2>
          <ol className="flex flex-col gap-2">
            {r.errors.map((e, i) => (
              <li key={i} className="rounded-2xl bg-soft p-3 text-sm">
                <span className="font-black">{i + 1}. </span>
                <span className="rounded bg-bad/15 px-1 font-bold line-through decoration-bad">{e.quote}</span>
                {" → "}
                <span className="rounded bg-good/20 px-1 font-black">{e.fix}</span>
                <span className="ml-2 text-xs font-extrabold uppercase text-muted">{t(`ielts.error_type.${e.type}`)}</span>
                {e.explanation && <p className="mt-1 font-bold text-muted">{e.explanation}</p>}
              </li>
            ))}
          </ol>
        </section>
      )}

      {r.improved && (
        <section className="card flex flex-col gap-2">
          <h2 className="text-lg font-black">🌟 {t("ielts.improved")}</h2>
          <p className="whitespace-pre-wrap font-bold leading-relaxed">{r.improved}</p>
        </section>
      )}
    </>
  );
}

export function Writing({ initial, onChange }: { initial: IeltsAttempt; onChange: (a: IeltsAttempt) => void }) {
  const t = useT();
  const [text, setText] = useState(String(initial.answers.text ?? ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(true);
  const minutes = initial.limits?.minutes ?? 40;
  const minWords = initial.limits?.min_words ?? 250;
  const endAt = useMemo(() => new Date(initial.started_at).getTime() + minutes * 60_000, [initial.started_at, minutes]);
  const [left, setLeft] = useState(() => Math.round((endAt - Date.now()) / 1000));
  const lastSaved = useRef(text);

  useEffect(() => {
    const id = setInterval(() => setLeft(Math.round((endAt - Date.now()) / 1000)), 1000);
    return () => clearInterval(id);
  }, [endAt]);

  // Черновик — на сервер через 3 секунды после паузы в наборе
  useEffect(() => {
    if (initial.status !== "active" || text === lastSaved.current) return;
    setSaved(false);
    const id = setTimeout(async () => {
      try {
        await api(`/ielts/attempts/${initial.id}/draft`, { method: "PUT", json: { text } });
        lastSaved.current = text;
        setSaved(true);
      } catch {
        /* повторим при следующей правке */
      }
    }, 3000);
    return () => clearTimeout(id);
  }, [text, initial.id, initial.status]);

  if (initial.status === "done") return <Result attempt={initial} />;

  const words = countWords(text);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<IeltsAttempt>(`/ielts/attempts/${initial.id}/submit`, { method: "POST", json: { text } }));
    } catch (e) {
      setError(errorCode(e));
      setBusy(false);
    }
  };

  return (
    <>
      {busy && <Thinking title={t("ielts.grading")} />}
      <section className="card flex flex-col gap-3">
        <span className="label !mb-0">Writing Task {initial.material.task}</span>
        <p className="whitespace-pre-wrap font-bold leading-relaxed">{initial.material.prompt}</p>
        {initial.material.chart && <IeltsChart chart={initial.material.chart} />}
      </section>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <div className="sticky top-0 z-10 -mx-4 flex items-center gap-3 bg-bg px-4 py-2 text-sm font-extrabold">
        <span className={left < 0 ? "text-bad" : ""} aria-label={t("dtm.time_left")}>⏱ {clock(left)}</span>
        <span className={words < minWords ? "text-muted" : "text-good"}>
          {t("ielts.word_count", { n: words, min: minWords })}
        </span>
        <span className="ml-auto text-muted">{saved ? `✓ ${t("ielts.saved")}` : <Dots />}</span>
      </div>
      {left < 0 && <Notice>{t("ielts.time_over")}</Notice>}

      <textarea
        className="field min-h-[22rem] resize-y font-body text-base leading-relaxed"
        value={text}
        onChange={(e) => setText(e.target.value.slice(0, 6000))}
        placeholder={t("ielts.essay_placeholder")}
        aria-label={t("ielts.your_essay")}
        spellCheck={false}
        lang="en"
      />
      <button type="button" className="btn btn-primary btn-xl" onClick={submit} disabled={busy || words < 50}>
        📝 {words < 50 ? t("ielts.need_more", { n: 50 - words }) : t("ielts.submit")}
      </button>
      <p className="text-center text-xs font-bold text-muted">{t("ielts.submit_hint")}</p>
    </>
  );
}
