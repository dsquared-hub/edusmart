"use client";

/* Вечерний мини-тест (Модуль 4): ~2 минуты, 17:00–22:00. Ошибаться можно:
   после ошибки — объяснение и вторая попытка, за исправление тоже монеты.
   Junior (до 7 класса) — крупные кнопки и озвучка вопроса; Senior — таймер. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Mascot } from "@/components/Mascot";
import { RequireStudent } from "@/components/RequireStudent";
import { Dots, IconButton, Notice, Page, ProgressBar, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { celebrate } from "@/lib/confetti";
import { useT } from "@/lib/i18n";

type Question = {
  slot: number;
  total: number;
  question: string;
  options: string[];
  difficulty: number;
  review: boolean;
  topic: string;
  retry: boolean;
};
type Status = { open: boolean; window: [string, string]; test: { id: number; status: string; score: number; total: number } | null; question?: Question | null };
type Summary = { score: number; total: number; corrected: number; topics_total: number; topics_understood: number; weak_topic: string | null };
type AnswerResult = {
  correct: boolean;
  retry: boolean;
  explanation: string | null;
  correct_option: number | null;
  points: number;
  finished: boolean;
  question?: Question;
  summary?: Summary;
};

const SPEECH_LANG: Record<string, string> = { ru: "ru-RU", uz: "uz-UZ", en: "en-US" };

function speak(text: string, lang: string) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = SPEECH_LANG[lang] ?? "ru-RU";
    u.rate = 0.95;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch {
    /* браузер без синтеза речи — просто без озвучки */
  }
}

function EveningView() {
  const t = useT();
  const { me } = useAuth();
  const junior = (me?.student?.grade ?? 5) <= 7;
  const [status, setStatus] = useState<Status | null>(null);
  const [testId, setTestId] = useState<number | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [earned, setEarned] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const shownAt = useRef(Date.now());

  useEffect(() => {
    api<Status>("/v1/evening")
      .then((s) => {
        setStatus(s);
        if (s.test?.status === "active" && s.question) {
          setTestId(s.test.id);
          setQuestion(s.question);
        }
      })
      .catch((e) => setError(errorCode(e)));
  }, []);

  // Новый вопрос: засекаем время (для ERS — скорость), Junior — озвучиваем
  useEffect(() => {
    if (!question) return;
    shownAt.current = Date.now();
    setElapsed(0);
    if (junior) speak(question.question, t.lang);
  }, [question, junior, t.lang]);

  // Таймер Senior-режима — только для информации, без ограничения по времени
  useEffect(() => {
    if (junior || !question || summary) return;
    const id = window.setInterval(() => setElapsed(Math.round((Date.now() - shownAt.current) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, [junior, question, summary]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ id: number; question: Question }>("/v1/evening/start", { method: "POST" });
      setTestId(r.id);
      setQuestion(r.question);
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  const answer = useCallback(
    async (option: number) => {
      if (!question || !testId || busy) return;
      setBusy(true);
      setPicked(option);
      try {
        const r = await api<AnswerResult>(`/v1/evening/${testId}/answer`, {
          method: "POST",
          json: { slot: question.slot, option, time_ms: Date.now() - shownAt.current },
        });
        setEarned((n) => n + r.points);
        setFeedback(r);
        if (r.finished && r.summary) {
          setSummary(r.summary);
          celebrate();
        }
      } catch (e) {
        setError(errorCode(e));
      } finally {
        setBusy(false);
      }
    },
    [question, testId, busy],
  );

  const next = () => {
    if (!feedback) return;
    if (feedback.retry && question) {
      setQuestion({ ...question, retry: true }); // тот же вопрос — вторая попытка
    } else if (feedback.question) {
      setQuestion(feedback.question);
    }
    setFeedback(null);
    setPicked(null);
  };

  if (!status && !error) return <Splash />;

  const big = junior ? "min-h-[4.5rem] text-2xl" : "min-h-[3.5rem] text-lg";

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="flex-1 text-2xl font-black">🌙 {t("evening.title")}</h1>
        {earned > 0 && <span className="rounded-full bg-accent/30 px-3 py-1 font-black">+{earned} ⭐</span>}
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {summary ? (
        <section className="card flex flex-col items-center gap-4 text-center">
          <Mascot mood="cheer" size={140} className="anim-pop" />
          <h2 className="text-3xl font-black">{t("evening.done_title")}</h2>
          <p className="text-lg font-bold">{t("evening.understood", { n: summary.topics_understood, total: summary.topics_total })}</p>
          <p className="font-semibold text-muted">{t("evening.score", { score: summary.score, total: summary.total, fixed: summary.corrected })}</p>
          {summary.weak_topic && <Notice>{t("evening.weak", { topic: summary.weak_topic })}</Notice>}
          <a href="/" className="btn btn-primary w-full">{t("done.home")}</a>
        </section>
      ) : question ? (
        <section className="flex flex-col gap-4">
          <ProgressBar value={question.slot} total={question.total} label={t("evening.progress", { n: question.slot + 1, total: question.total })} />
          <div className="card flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2 text-sm font-extrabold text-muted">
              <span>{question.review ? `🔁 ${t("evening.review")}` : `📘 ${question.topic}`}</span>
              <span>· {"★".repeat(question.difficulty)}{"☆".repeat(3 - question.difficulty)}</span>
              {!junior && <span className="ml-auto tabular-nums">⏱ {elapsed}s</span>}
            </div>
            <h2 className={`font-black leading-snug ${junior ? "text-3xl" : "text-2xl"}`}>{question.question}</h2>
            {junior && (
              <button className="self-start text-sm font-extrabold text-primary underline underline-offset-4" onClick={() => speak(question.question, t.lang)}>
                🔊 {t("evening.listen")}
              </button>
            )}
            {question.retry && !feedback && <Notice>{t("evening.try_again")}</Notice>}
          </div>
          <div className="grid gap-3">
            {question.options.map((o, i) => {
              const state =
                feedback && picked === i ? (feedback.correct ? "correct" : "wrong") : feedback?.correct_option === i ? "correct" : undefined;
              return (
                <button key={i} className={`option ${big}`} data-state={state} disabled={busy || !!feedback} onClick={() => answer(i)}>
                  <span className="option-letter">{"ABCD"[i]}</span>
                  <span className="flex-1">{o}</span>
                </button>
              );
            })}
          </div>
          {feedback && (
            <div className="card flex flex-col gap-3 anim-rise" aria-live="polite">
              <div className="text-xl font-black">
                {feedback.correct ? `✅ ${t("evening.correct", { n: feedback.points })}` : feedback.retry ? `💡 ${t("evening.almost")}` : `🤝 ${t("evening.next_time")}`}
              </div>
              {feedback.explanation && <p className="font-semibold">{feedback.explanation}</p>}
              <button className="btn btn-primary" onClick={next}>
                {feedback.retry ? t("evening.retry") : t("step.next")}
              </button>
            </div>
          )}
        </section>
      ) : (
        <section className="card flex flex-col items-center gap-4 text-center">
          <Mascot size={120} className="anim-bob" />
          <h2 className="text-2xl font-black">{t("evening.intro_title")}</h2>
          <p className="font-semibold text-muted">{t("evening.intro")}</p>
          {status?.test?.status === "finished" ? (
            <Notice>{t("evening.already_done", { score: status.test.score, total: status.test.total })}</Notice>
          ) : status?.open ? (
            <button className={`btn btn-primary w-full ${junior ? "btn-xl" : ""}`} onClick={start} disabled={busy}>
              {busy ? <Dots /> : `🌙 ${t("evening.start")}`}
            </button>
          ) : (
            <Notice>{t("evening.closed", { from: status?.window[0] ?? "17:00", to: status?.window[1] ?? "22:00" })}</Notice>
          )}
        </section>
      )}
    </Page>
  );
}

export default function EveningPage() {
  return (
    <RequireStudent>
      <EveningView />
    </RequireStudent>
  );
}
