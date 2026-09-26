"use client";

/* IELTS Speaking: экзаменатор задаёт вопрос голосом, ученик отвечает в микрофон.
   После каждого ответа — расшифровка, ошибки и советы по произношению; в конце — Band
   по 4 критериям от двух экзаменаторов. Part 2 — карточка: минута на подготовку, до 2 минут речи. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Thinking } from "@/components/Thinking";
import { Dots, Notice } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { IeltsAttempt } from "@/lib/types";
import { toWav } from "@/lib/wav";

type Step = { part: number; question: string };
type Turn = Step & {
  transcript: string;
  grammar: { quote: string; fix: string; explanation: string }[];
  vocabulary: { quote: string; better: string }[];
  pronunciation: { word: string; tip: string }[];
  comment: string;
};
type SpeakingResult = {
  criteria: Record<"FC" | "LR" | "GRA" | "P", { band: number; comment: string }>;
  examiners: Record<"A" | "B", Record<string, number>>;
  summary: string;
};

const CRITERIA = ["FC", "LR", "GRA", "P"] as const;
const PREP_SECONDS = 60;

function say(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const voice = synth.getVoices().find((v) => v.lang === "en-GB") ?? synth.getVoices().find((v) => v.lang.startsWith("en"));
  if (voice) u.voice = voice;
  u.lang = voice?.lang ?? "en-GB";
  u.rate = 0.95;
  synth.speak(u);
}

function Feedback({ turn }: { turn: Turn }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-2 text-sm">
      <p className="rounded-2xl bg-soft p-3 font-bold italic" lang="en">“{turn.transcript}”</p>
      {turn.grammar.map((g, i) => (
        <p key={`g${i}`}>
          ✏️ <span className="rounded bg-bad/15 px-1 font-bold line-through decoration-bad">{g.quote}</span> →{" "}
          <span className="rounded bg-good/20 px-1 font-black">{g.fix}</span> <span className="text-muted">{g.explanation}</span>
        </p>
      ))}
      {turn.vocabulary.map((v, i) => (
        <p key={`v${i}`}>📚 {v.quote} → <b>{v.better}</b></p>
      ))}
      {turn.pronunciation.map((p, i) => (
        <p key={`p${i}`}>🗣️ <b>{p.word}</b>: {p.tip}</p>
      ))}
      {turn.comment && <p className="font-bold text-muted">💬 {turn.comment}</p>}
      {!turn.grammar.length && !turn.pronunciation.length && <p className="font-bold text-good">✅ {t("ielts.no_mistakes")}</p>}
    </div>
  );
}

function Result({ attempt, turns }: { attempt: IeltsAttempt; turns: Turn[] }) {
  const t = useT();
  const r = attempt.result as unknown as SpeakingResult;
  return (
    <>
      <section className="card flex flex-col items-center gap-1 text-center anim-pop">
        <span className="text-sm font-extrabold uppercase text-muted">Speaking Band</span>
        <span className="text-6xl font-black text-primary">{attempt.band?.toFixed(1)}</span>
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
      {r.summary && <Notice>💡 {r.summary}</Notice>}
      <ol className="flex flex-col gap-3">
        {turns.map((turn, i) => (
          <li key={i} className="card flex flex-col gap-2">
            <span className="text-xs font-extrabold text-muted">Part {turn.part}</span>
            <p className="font-black" lang="en">{turn.question}</p>
            <Feedback turn={turn} />
          </li>
        ))}
      </ol>
    </>
  );
}

export function Speaking({ initial, onChange }: { initial: IeltsAttempt; onChange: (a: IeltsAttempt) => void }) {
  const t = useT();
  const plan = (initial as IeltsAttempt & { plan?: Step[] }).plan ?? [];
  const turns = ((initial.answers?.turns as Turn[]) ?? []);
  const index = turns.length;
  const step = plan[index];
  const last = turns[turns.length - 1];
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [prep, setPrep] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const limit = step?.part === 2 ? 120 : 60;

  // Вопрос экзаменатора — голосом; для Part 2 — минута на подготовку
  useEffect(() => {
    if (!step || initial.status !== "active") return;
    say(step.question);
    setPrep(step.part === 2 ? PREP_SECONDS : null);
  }, [step, initial.status]);

  useEffect(() => {
    if (prep === null || prep <= 0) return;
    const id = setTimeout(() => setPrep((p) => (p === null ? null : p - 1)), 1000);
    return () => clearTimeout(id);
  }, [prep]);

  const send = useCallback(
    async (recorded: Blob) => {
      setBusy(true);
      setError(null);
      try {
        const form = new FormData();
        form.set("turn", String(index));
        form.set("audio", await toWav(recorded), "answer.wav");
        onChange(await api<IeltsAttempt>(`/ielts/attempts/${initial.id}/speak`, { method: "POST", form }));
      } catch (e) {
        setError(errorCode(e));
      } finally {
        setBusy(false);
      }
    },
    [index, initial.id, onChange],
  );

  const stop = useCallback(() => {
    recorder.current?.stop();
    setRecording(false);
  }, []);

  useEffect(() => {
    if (!recording) return;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [recording]);

  useEffect(() => {
    if (recording && seconds >= limit) stop(); // регламент: Part 2 — до 2 минут, остальное — до минуты
  }, [recording, seconds, limit, stop]);

  const start = async () => {
    setError(null);
    window.speechSynthesis?.cancel();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        void send(new Blob(chunks.current, { type: rec.mimeType }));
      };
      recorder.current = rec;
      rec.start();
      setSeconds(0);
      setPrep(null);
      setRecording(true);
    } catch {
      setError("mic_denied");
    }
  };

  const grade = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<IeltsAttempt>(`/ielts/attempts/${initial.id}/grade`, { method: "POST" }));
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  if (initial.status === "done") return <Result attempt={initial} turns={turns} />;

  return (
    <>
      {busy && <Thinking title={index === plan.length - 1 ? t("ielts.grading_speaking") : t("ielts.listening_answer")} />}
      <div className="flex gap-1" aria-hidden="true">
        {plan.map((_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full ${i < index ? "bg-primary" : "bg-line"}`} />
        ))}
      </div>

      {last && (
        <section className="card flex flex-col gap-2">
          <span className="text-xs font-extrabold text-muted">{t("ielts.last_answer")}</span>
          <Feedback turn={last} />
        </section>
      )}

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {step ? (
        <section className="card flex flex-col items-center gap-3 text-center">
          <span className="chip">Part {step.part} · {index + 1}/{plan.length}</span>
          {step.part === 2 ? (
            <div className="w-full rounded-2xl bg-soft p-4 text-left" lang="en">
              <p className="font-black">{step.question.split(". You should say:")[0]}</p>
              <p className="mt-2 text-sm font-extrabold text-muted">You should say:</p>
              <ul className="list-disc pl-5 text-sm font-bold">
                {(step.question.split("You should say: ")[1] ?? "").split("; ").map((p) => <li key={p}>{p}</li>)}
              </ul>
            </div>
          ) : (
            <p className="text-xl font-black" lang="en">{step.question}</p>
          )}
          <button type="button" className="btn btn-soft !min-h-[2.5rem] !w-auto px-4 text-sm" onClick={() => say(step.question)} disabled={recording}>
            🔊 {t("ielts.repeat_question")}
          </button>
          {prep !== null && prep > 0 && !recording && <p className="font-black text-primary">⏳ {t("ielts.prep", { n: prep })}</p>}
          {recording ? (
            <button type="button" className="btn btn-primary btn-xl" onClick={stop}>
              ⏹ {t("ielts.stop_answer")} · {seconds}s / {limit}s
            </button>
          ) : (
            <button type="button" className="btn btn-primary btn-xl" onClick={start} disabled={busy}>
              🎙️ {t("ielts.answer")}
            </button>
          )}
          <p className="text-xs font-bold text-muted">🔒 {t("ielts.audio_note")}</p>
        </section>
      ) : (
        <button type="button" className="btn btn-primary btn-xl" onClick={grade} disabled={busy}>
          {busy ? <Dots /> : `📊 ${t("ielts.get_band")}`}
        </button>
      )}
    </>
  );
}
