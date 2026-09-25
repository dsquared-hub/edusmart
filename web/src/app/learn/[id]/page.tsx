"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DoneScreen } from "@/components/lesson/DoneScreen";
import { PracticeScreen } from "@/components/lesson/PracticeScreen";
import { StepScreen } from "@/components/lesson/StepScreen";
import { RequireStudent } from "@/components/RequireStudent";
import { Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import type { AnswerResult, Topic } from "@/lib/types";

type View = "steps" | "done" | "practice";

function Lesson({ id }: { id: string }) {
  const t = useT();
  const { me, refresh } = useAuth();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("steps");
  const [resultTotals, setResultTotals] = useState<{ points: number; level: number; streak: number } | null>(null);

  // Тема хранится на сервере — её можно продолжить здесь после бота и наоборот
  useEffect(() => {
    api<Topic>(`/explain/${id}`)
      .then((data) => {
        setTopic(data);
        if (data.status === "completed") {
          setView("done");
          refresh().catch(() => undefined); // свежие очки для итогов
        }
      })
      .catch((e) => setError(errorCode(e)));
  }, [id, refresh]);

  // Итоги: из ответа сервера, если тему закрыли только что, иначе — из профиля
  const totals =
    resultTotals ??
    (me?.student ? { points: me.student.points, level: me.student.level, streak: me.student.streak } : null);

  // Тему закрыли в другом месте (например, в боте), пока она была открыта здесь
  const onClosed = (fresh: Topic) => {
    setTopic(fresh);
    setView("done");
    refresh().catch(() => undefined);
  };

  const onCompleted = (result: AnswerResult) => {
    setTopic(result.topic);
    setResultTotals({ points: result.total_points, level: result.level, streak: result.streak });
    setView("done");
    refresh().catch(() => undefined);
  };

  if (error) {
    return (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/" className="btn btn-soft">🏠 {t("done.home")}</Link>
      </Page>
    );
  }
  if (!topic) return <Splash />;

  if (topic.status === "abandoned" || topic.total_steps === 0) {
    return (
      <Page className="justify-center gap-4">
        <Notice>{t("errors.topic_not_found")}</Notice>
        <Link href="/learn" className="btn btn-primary">🤔 {t("done.new_topic")}</Link>
      </Page>
    );
  }

  return (
    <Page className="pt-0">
      {view === "steps" && (
        <StepScreen topic={topic} onTopic={setTopic} onClosed={onClosed} onCompleted={onCompleted} />
      )}
      {view === "done" && <DoneScreen topic={topic} totals={totals} onPractice={() => setView("practice")} />}
      {view === "practice" && (
        <PracticeScreen
          topic={topic}
          onBack={() => setView("done")}
        />
      )}
    </Page>
  );
}

export default function LessonPage({ params }: { params: { id: string } }) {
  return (
    <RequireStudent>
      <Lesson id={params.id} />
    </RequireStudent>
  );
}
