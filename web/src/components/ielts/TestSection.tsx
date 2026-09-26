"use client";

/* IELTS Reading / Listening: текст или запись, вопросы трёх типов (выбор ответа,
   TRUE/FALSE/NOT GIVEN, впиши слово), мгновенная проверка и разбор с цитатой из текста.
   Запись Listening озвучивает браузер (разные голоса для собеседников); текст записи —
   только после сдачи, как на настоящем экзамене. */
import { useEffect, useRef, useState } from "react";
import { Thinking } from "@/components/Thinking";
import { Notice } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { IeltsAttempt } from "@/lib/types";

type Question = {
  type: "mcq" | "tfng" | "gap";
  text: string;
  options?: string[];
  answer?: number | string;
  alternatives?: string[];
  evidence?: string;
};
type Line = { speaker: string; text: string };
type Material = { title: string; passage?: string; context?: string; script?: Line[]; questions: Question[] };
type TestResult = { correct: number; total: number; marks: boolean[]; scaled: number };

const TFNG = ["TRUE", "FALSE", "NOT GIVEN"];
const LETTERS = ["A", "B", "C", "D"];

/** Озвучка записи голосами браузера: по голосу на собеседника, британский акцент — если есть. */
function useSpeech(script: Line[], context: string) {
  const [state, setState] = useState<"idle" | "playing" | "done" | "unsupported">("idle");
  const [plays, setPlays] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) setState("unsupported");
    return () => window.speechSynthesis?.cancel();
  }, []);

  const play = () => {
    const synth = window.speechSynthesis;
    const voices = synth.getVoices().filter((v) => v.lang.startsWith("en"));
    const british = voices.filter((v) => v.lang === "en-GB");
    const pool = british.length >= 2 ? british : voices;
    const speakers = [...new Set(script.map((l) => l.speaker))];
    synth.cancel();
    const lines = [{ speaker: "", text: context }, ...script];
    lines.forEach((line, i) => {
      const u = new SpeechSynthesisUtterance(line.text);
      const idx = line.speaker ? speakers.indexOf(line.speaker) : 0;
      u.voice = pool.length ? pool[idx % pool.length] : null;
      u.lang = u.voice?.lang ?? "en-GB";
      u.rate = 0.95;
      u.pitch = pool.length < 2 && idx % 2 === 1 ? 1.3 : 1; // один голос на устройстве — различаем высотой
      if (i === lines.length - 1) u.onend = () => setState("done");
      synth.speak(u);
    });
    setPlays((n) => n + 1);
    setState("playing");
  };

  const stop = () => {
    window.speechSynthesis.cancel();
    setState("done");
  };

  return { state, plays, play, stop };
}

function Player({ material }: { material: Material }) {
  const t = useT();
  const { state, plays, play, stop } = useSpeech(material.script ?? [], material.context ?? "");
  if (state === "unsupported") return <Notice tone="error">{t("ielts.no_speech")}</Notice>;
  return (
    <section className="card flex flex-col items-center gap-3 text-center">
      <span className="text-5xl" aria-hidden="true">🎧</span>
      <p className="font-bold">{material.context}</p>
      {state === "playing" ? (
        <button type="button" className="btn btn-soft" onClick={stop}>⏹ {t("ielts.stop")}</button>
      ) : (
        <button type="button" className="btn btn-primary" onClick={play}>
          ▶️ {plays === 0 ? t("ielts.listen") : t("ielts.listen_again")}
        </button>
      )}
      <p className="text-xs font-bold text-muted">{plays > 1 ? t("ielts.played", { n: plays }) : t("ielts.once_hint")}</p>
    </section>
  );
}

function QuestionInput({
  q,
  n,
  value,
  onChange,
  review,
}: {
  q: Question;
  n: number;
  value: number | string | null | undefined;
  onChange: (v: number | string) => void;
  review?: boolean;
}) {
  const t = useT();
  const state = (i: number | string) => {
    if (!review) return value === i ? "picked" : undefined;
    if (i === q.answer) return "correct";
    return value === i ? "wrong" : undefined;
  };
  return (
    <li className="card flex flex-col gap-2">
      <p className="font-black [overflow-wrap:anywhere]">
        {n + 1}. {q.text}
      </p>
      {q.type === "mcq" &&
        q.options?.map((o, i) => (
          <button
            key={i}
            type="button"
            disabled={review}
            onClick={() => onChange(i)}
            className={`option !min-h-[2.75rem] !text-base ${state(i) === "picked" ? "!border-primary !bg-primary/10" : ""}`}
            data-state={state(i) === "picked" ? undefined : state(i)}
          >
            <span className="option-letter">{LETTERS[i]}</span>
            <span className="min-w-0 flex-1">{o}</span>
          </button>
        ))}
      {q.type === "tfng" && (
        <div className="grid grid-cols-3 gap-2">
          {TFNG.map((v) => (
            <button
              key={v}
              type="button"
              disabled={review}
              onClick={() => onChange(v)}
              className={`option !min-h-[2.75rem] justify-center !px-2 !text-sm ${state(v) === "picked" ? "!border-primary !bg-primary/10" : ""}`}
              data-state={state(v) === "picked" ? undefined : state(v)}
            >
              {v}
            </button>
          ))}
        </div>
      )}
      {q.type === "gap" && (
        <input
          className="field"
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value.slice(0, 60))}
          disabled={review}
          placeholder={t("ielts.gap_placeholder")}
          lang="en"
          autoCapitalize="none"
          spellCheck={false}
        />
      )}
      {review && q.type === "gap" && (
        <p className="text-sm font-bold">✅ {String(q.answer)}{q.alternatives?.length ? ` / ${q.alternatives.join(" / ")}` : ""}</p>
      )}
      {review && q.evidence && <p className="rounded-xl bg-soft p-2 text-sm font-bold text-muted">📌 {q.evidence}</p>}
    </li>
  );
}

export function TestSection({ initial, onChange }: { initial: IeltsAttempt; onChange: (a: IeltsAttempt) => void }) {
  const t = useT();
  const material = initial.material as unknown as Material;
  const done = initial.status === "done";
  const [answers, setAnswers] = useState<Record<string, number | string>>(() => {
    const saved: Record<string, number | string> = {};
    Object.entries(initial.answers ?? {}).forEach(([k, v]) => {
      if (typeof v === "number" || typeof v === "string") saved[k] = v;
    });
    return saved;
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const result = initial.result as unknown as TestResult | null;

  const submit = async () => {
    const empty = material.questions.length - Object.values(answers).filter((v) => v !== "").length;
    if (empty > 0 && !window.confirm(t("dtm.confirm_unanswered", { n: empty }))) return;
    setBusy(true);
    setError(null);
    try {
      onChange(await api<IeltsAttempt>(`/ielts/attempts/${initial.id}/answers`, { method: "POST", json: { answers } }));
      top.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      setError(errorCode(e));
      setBusy(false);
    }
  };

  return (
    <>
      <div ref={top} />
      {busy && <Thinking title={t("quests.checking")} />}
      {done && result && (
        <section className="card flex flex-col items-center gap-1 text-center anim-pop">
          <span className="text-sm font-extrabold uppercase text-muted">Band</span>
          <span className="text-6xl font-black text-primary">{initial.band?.toFixed(1)}</span>
          <span className="font-bold">{t("ielts.correct", { n: result.correct, total: result.total })}</span>
          <span className="text-xs font-bold text-muted">{t("ielts.scaled", { n: result.scaled })}</span>
        </section>
      )}

      <h2 className="text-xl font-black">{material.title}</h2>
      {initial.kind === "reading" && material.passage && (
        <article className="card flex flex-col gap-3 leading-relaxed" lang="en">
          {material.passage.split(/\n\s*\n/).map((p, i) => (
            <p key={i} className="font-semibold">{p}</p>
          ))}
        </article>
      )}
      {initial.kind === "listening" && <Player material={material} />}
      {initial.kind === "listening" && done && material.script && (
        <details className="card">
          <summary className="cursor-pointer font-black">📜 {t("ielts.transcript")}</summary>
          <div className="mt-2 flex flex-col gap-1 text-sm" lang="en">
            {material.script.map((l, i) => (
              <p key={i}><b>{l.speaker}:</b> {l.text}</p>
            ))}
          </div>
        </details>
      )}

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <ol className="flex flex-col gap-3" lang="en">
        {material.questions.map((q, i) => (
          <QuestionInput
            key={i}
            q={q}
            n={i}
            value={answers[String(i)]}
            onChange={(v) => setAnswers((a) => ({ ...a, [String(i)]: v }))}
            review={done}
          />
        ))}
      </ol>

      {!done && (
        <button type="button" className="btn btn-primary btn-xl" onClick={submit} disabled={busy}>
          ✅ {t("ielts.check")}
        </button>
      )}
    </>
  );
}
