"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Mascot } from "@/components/Mascot";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, ProgressBar } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { celebrate } from "@/lib/confetti";
import { useT } from "@/lib/i18n";
import { haptic } from "@/lib/telegram";
import type { PracticeTask, Topic } from "@/lib/types";
import { Options, type OptionState } from "./Options";
import { ReportButton } from "./ReportButton";

/** «Закрепить ещё 3 задачами»: проверка сразу на месте, при ошибке — подсказка. */
export function PracticeScreen({ topic, onBack }: { topic: Topic; onBack: () => void }) {
  const t = useT();
  const [tasks, setTasks] = useState<PracticeTask[] | null>(topic.practice);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [wrong, setWrong] = useState<number[]>([]);
  const [solved, setSolved] = useState(false);
  const [shake, setShake] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    if (tasks) return;
    api<{ tasks: PracticeTask[] }>(`/explain/${topic.id}/practice`, { method: "POST" })
      .then((r) => setTasks(r.tasks))
      .catch((e) => setError(errorCode(e)));
  }, [tasks, topic.id]);

  useEffect(() => {
    if (finished) celebrate(false);
  }, [finished]);

  if (error) {
    return (
      <div className="flex flex-col gap-4 py-6">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <button className="btn btn-soft" onClick={onBack}>‹ {t("profile.back")}</button>
      </div>
    );
  }
  if (!tasks) return <Thinking title={t("practice.loading")} />;

  if (finished) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-5 py-6 text-center">
        <Mascot mood="cheer" size={130} className="anim-pop" />
        <h1 className="text-3xl font-black">💪 {t("practice.finish_title")}</h1>
        <p className="text-lg font-bold text-muted">{t("practice.finish_text")}</p>
        <div className="flex w-full flex-col gap-3">
          <Link href="/learn" className="btn btn-primary btn-xl">🤔 {t("done.new_topic")}</Link>
          <Link href="/" className="btn btn-soft">🏠 {t("done.home")}</Link>
        </div>
      </div>
    );
  }

  const task = tasks[index];
  const states: OptionState[] = task.options.map((_, i) =>
    solved && i === task.correct ? "correct" : wrong.includes(i) ? "wrong" : solved ? "dim" : "idle",
  );

  const pick = (option: number) => {
    if (solved) return;
    if (option === task.correct) {
      haptic("success");
      setSolved(true);
    } else {
      haptic("error");
      setWrong((w) => [...w, option]);
      setShake(option);
      setTimeout(() => setShake(null), 450);
    }
  };

  const next = () => {
    if (index + 1 >= tasks.length) {
      setFinished(true);
      return;
    }
    setIndex(index + 1);
    setWrong([]);
    setSolved(false);
  };

  return (
    <div className="flex flex-1 flex-col gap-4 pb-40">
      <div className="sticky top-0 z-20 -mx-4 flex items-center gap-3 bg-bg/95 px-4 py-3 backdrop-blur">
        <IconButton onClick={onBack} label={t("profile.back")}>‹</IconButton>
        <div className="flex-1">
          <ProgressBar
            value={index + (solved ? 1 : 0)}
            total={tasks.length}
            label={`${t("practice.title")} · ${t("practice.task_of", { n: index + 1, total: tasks.length })}`}
          />
        </div>
      </div>

      <article key={index} className="card flex flex-col gap-4 anim-rise">
        <p className="text-2xl font-black leading-snug">{task.question}</p>
      </article>

      <Options options={task.options} states={states} disabled={solved} onPick={pick} shakeIndex={shake} />
      <ReportButton key={index} topicId={topic.id} index={index} kind="practice" />

      {wrong.length > 0 && !solved && task.hint && (
        <Notice>
          💡 <b>{t("practice.hint")}:</b> {task.hint}
        </Notice>
      )}

      <div aria-live="assertive" className="fixed inset-x-0 bottom-0 z-30">
        {solved && (
          <div className="safe-bottom border-t-[length:var(--border-w)] border-good bg-surface px-4 pt-4 anim-rise">
            <div className="mx-auto flex max-w-app flex-col gap-3">
              <div className="text-2xl font-black text-good">{t("practice.correct")}</div>
              <button className="btn btn-good" onClick={next} autoFocus>
                {index + 1 >= tasks.length ? `🏁 ${t("step.finish")}` : `${t("practice.next")} →`}
              </button>
            </div>
          </div>
        )}
        {!solved && wrong.length > 0 && (
          <p className="sr-only">{t("practice.wrong")}</p>
        )}
      </div>
    </div>
  );
}
