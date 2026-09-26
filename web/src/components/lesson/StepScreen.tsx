"use client";

import { useEffect, useRef, useState } from "react";
import { Mascot } from "@/components/Mascot";
import { Dots, IconButton, Notice, ProgressBar } from "@/components/ui";
import { Visual } from "@/components/visuals/Visual";
import { api, ApiError, errorCode } from "@/lib/api";
import { celebrate } from "@/lib/confetti";
import { useT } from "@/lib/i18n";
import { subjectIcon } from "@/lib/subjects";
import { haptic } from "@/lib/telegram";
import type { AnswerResult, SimplerStep, Topic } from "@/lib/types";
import { Options, type OptionState } from "./Options";
import { ReportButton } from "./ReportButton";

type Phase = "question" | "checking" | "correct" | "wrong" | "simplifying";

/**
 * Экран шага: заголовок, короткий текст, пример, схема, мини-проверка.
 * Верно → +10 и «Дальше». Неверно → «Объясни проще» → тот же вопрос снова.
 */
export function StepScreen({
  topic,
  onTopic,
  onClosed,
  onCompleted,
}: {
  topic: Topic;
  onTopic: (topic: Topic) => void;
  onClosed: (topic: Topic) => void;
  onCompleted: (result: AnswerResult) => void;
}) {
  const t = useT();
  const [index, setIndex] = useState(topic.current_step);
  const [phase, setPhase] = useState<Phase>("question");
  const [picked, setPicked] = useState<number | null>(null);
  const [shake, setShake] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [notice, setNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [floatKey, setFloatKey] = useState(0);
  const top = useRef<HTMLDivElement>(null);

  const step = topic.steps[index];
  const simpler: SimplerStep | null | undefined = step?.simpler;
  const shown = simpler && !showOriginal ? simpler : step;
  const doneSteps = index + (phase === "correct" ? 1 : 0);
  const simplifyLeft = step?.simplify_left ?? 1;

  useEffect(() => {
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [index]);

  if (!step || !shown) return null;

  const states: OptionState[] = step.options.map((_, i) => {
    if (i !== picked) return phase === "correct" ? "dim" : "idle";
    if (phase === "correct") return "correct";
    if (phase === "wrong" || phase === "simplifying") return "wrong";
    return "idle";
  });

  const goToServerStep = (fresh: Topic) => {
    if (fresh.status !== "in_progress") {
      onClosed(fresh);
      return;
    }
    onTopic(fresh);
    setIndex(fresh.current_step);
    setPhase("question");
    setPicked(null);
    setShowOriginal(false);
  };

  const pick = async (option: number) => {
    if (phase !== "question") return;
    setPicked(option);
    setPhase("checking");
    setNotice(null);
    try {
      const res = await api<AnswerResult>(`/explain/${topic.id}/answer`, {
        method: "POST",
        json: { step: index, option },
      });
      if (res.correct) {
        haptic("success");
        setResult(res);
        onTopic(res.topic);
        setPhase("correct");
        setFloatKey((k) => k + 1);
        celebrate(false); // небольшой салют — радость без перегруза
      } else {
        haptic("error");
        setShake(option);
        setTimeout(() => setShake(null), 450);
        setPhase("wrong");
      }
    } catch (err) {
      if (err instanceof ApiError && (err.code === "stale_step" || err.code === "topic_closed")) {
        const fresh = err.detail.topic as Topic | undefined;
        if (fresh) {
          setNotice({ tone: "info", text: t("step.stale") });
          goToServerStep(fresh);
          return;
        }
      }
      setNotice({ tone: "error", text: t(`errors.${errorCode(err)}`) });
      setPhase("question");
      setPicked(null);
    }
  };

  const simplify = async () => {
    setPhase("simplifying");
    try {
      const res = await api<{ simpler: SimplerStep }>(`/explain/${topic.id}/simplify`, { method: "POST" });
      const steps = topic.steps.map((s, i) =>
        i === index ? { ...s, simpler: res.simpler, simplify_left: Math.max(0, simplifyLeft - 1) } : s,
      );
      onTopic({ ...topic, steps });
      setShowOriginal(false);
      setNotice({ tone: "info", text: t("step.try_again") });
      setPicked(null);
      setPhase("question");
      top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      if (errorCode(err) === "simplify_limit") {
        // Лимит упрощений: больше не тратим запросы, просим перечитать шаг
        const steps = topic.steps.map((s, i) => (i === index ? { ...s, simplify_left: 0 } : s));
        onTopic({ ...topic, steps });
        setNotice({ tone: "info", text: t("step.simplify_none") });
      } else {
        // Модель не ответила — не блокируем ребёнка: можно перечитать шаг и ответить снова
        setNotice({ tone: "error", text: `${t(`errors.${errorCode(err)}`)} ${t("step.try_again")}` });
      }
      setPicked(null);
      setPhase("question");
    }
  };

  const retry = () => {
    setNotice({ tone: "info", text: t("step.simplify_none") });
    setPicked(null);
    setPhase("question");
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const next = () => {
    if (!result) return;
    if (result.completed) {
      onCompleted(result);
      return;
    }
    setIndex(result.topic.current_step);
    setPhase("question");
    setPicked(null);
    setResult(null);
    setShowOriginal(false);
    setNotice(null);
  };

  return (
    <div className="flex flex-1 flex-col gap-4 pb-40">
      <div ref={top} className="sticky top-0 z-20 -mx-4 flex items-center gap-3 bg-bg/95 px-4 py-3 backdrop-blur">
        <IconButton href="/" label={t("step.close")}>✕</IconButton>
        <div className="flex-1">
          <ProgressBar
            value={doneSteps}
            total={topic.total_steps}
            label={t("step.progress", { n: index + 1, total: topic.total_steps })}
          />
        </div>
        <div className="relative shrink-0 rounded-2xl bg-soft px-3 py-2 text-lg font-black">
          ⭐ {topic.points_earned}
          {phase === "correct" && result && result.points_awarded > 0 && (
            <span key={floatKey} className="anim-float-up pointer-events-none absolute -top-2 left-1/2 -translate-x-1/2 whitespace-nowrap text-xl font-black text-good">
              {t("step.correct_points", { points: result.points_awarded })}
            </span>
          )}
        </div>
      </div>

      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}

      {/* Шаг — карточка из «колоды»: сзади выглядывают оставшиеся шаги */}
      <div className="step-deck" data-left={Math.min(2, topic.total_steps - index - 1)}>
        <article key={`${index}-${simpler && !showOriginal ? "s" : "o"}`} className="card step-card flex flex-col gap-4 anim-card-in">
          {topic.title && (
            <span className="step-badge max-w-full truncate">
              {subjectIcon(topic.subject)} {topic.title}
            </span>
          )}
          {simpler && (
            <div className="flex items-center justify-between gap-2">
              {!showOriginal ? (
                <span className="rounded-full bg-accent px-3 py-1 text-sm font-black text-ink">🐢 {t("step.simpler_badge")}</span>
              ) : (
                <span />
              )}
              <button
                type="button"
                className="text-sm font-extrabold text-primary underline underline-offset-4"
                onClick={() => setShowOriginal((v) => !v)}
              >
                {showOriginal ? t("step.show_simpler") : t("step.show_original")}
              </button>
            </div>
          )}
          <h1 className="text-3xl font-black leading-tight">{shown.title}</h1>
          <p className="text-xl font-semibold leading-relaxed">{shown.text}</p>
          <Visual visual={shown.visual} />
          <div className="rounded-2xl bg-accent/20 p-4">
            <div className="mb-1 text-sm font-black uppercase tracking-wide text-muted">💡 {t("step.example")}</div>
            <p className="text-lg font-bold">{shown.example}</p>
          </div>
        </article>
      </div>

      <section className="check-card flex flex-col gap-3" aria-labelledby="check-q">
        <div className="flex items-center gap-3">
          <Mascot mood={phase === "correct" ? "cheer" : "thinking"} size={56} />
          <div className="min-w-0 flex-1">
            <h2 className="label !mb-1">❓ {t("step.check")}</h2>
            <p id="check-q" className="text-xl font-extrabold">{step.check_question}</p>
          </div>
        </div>
        <Options
          options={step.options}
          states={states}
          shakeIndex={shake}
          disabled={phase !== "question"}
          onPick={pick}
        />
        <ReportButton key={index} topicId={topic.id} index={index} />
      </section>

      {/* Панель обратной связи снизу — как в играх: крупно и сразу понятно */}
      <div aria-live="assertive" className="fixed inset-x-0 bottom-0 z-30">
        {phase === "correct" && result && (
          <div className="safe-bottom border-t-[length:var(--border-w)] border-good bg-surface px-4 pt-4 anim-rise">
            <div className="mx-auto flex max-w-app flex-col gap-3">
              <div className="flex items-center gap-2 text-2xl font-black text-good">
                🎉 {t("step.correct")}
                {result.points_awarded > 0 && (
                  <span className="text-ink">{t("step.correct_points", { points: result.points_awarded })}</span>
                )}
              </div>
              {result.points_awarded === 0 && <p className="font-bold text-muted">{t("step.no_points")}</p>}
              {result.points_awarded > 0 && result.attempts === 2 && (
                <p className="font-bold text-muted">{t("step.second_try")}</p>
              )}
              <button className="btn btn-good" onClick={next} autoFocus>
                {result.completed ? `🏁 ${t("step.finish")}` : `${t("step.next")} →`}
              </button>
            </div>
          </div>
        )}
        {(phase === "wrong" || phase === "simplifying") && (
          <div className="safe-bottom border-t-[length:var(--border-w)] border-bad bg-surface px-4 pt-4 anim-rise">
            <div className="mx-auto flex max-w-app flex-col gap-3">
              <div className="text-xl font-black text-bad">🤔 {t("step.wrong")}</div>
              {simplifyLeft > 0 ? (
                <button className="btn btn-primary" onClick={simplify} disabled={phase === "simplifying"}>
                  {phase === "simplifying" ? (
                    <>
                      <Dots /> <span>{t("step.simplifying")}</span>
                    </>
                  ) : (
                    `🐢 ${t("step.simplify")}`
                  )}
                </button>
              ) : (
                <button className="btn btn-primary" onClick={retry}>
                  🔁 {t("step.retry")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
