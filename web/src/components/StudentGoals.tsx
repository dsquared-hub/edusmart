"use client";

/* Главная ученика: задания от родителя / учителя (открывают «Объясни тему» с этой темой)
   и Exam Readiness Score по предметам — сколько процентов готовности к экзамену. */
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { ReadinessSubject } from "@/lib/types";

type Assignment = { id: number; topic_id: number; topic: string; note: string | null; created_at: string };

function Bar({ value }: { value: number }) {
  const tone = value >= 80 ? "bg-good" : value >= 50 ? "bg-accent" : "bg-bad";
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
      <div className={`h-full rounded-full ${tone} transition-all duration-700`} style={{ width: `${Math.max(3, value)}%` }} />
    </div>
  );
}

export function StudentGoals() {
  const t = useT();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [readiness, setReadiness] = useState<ReadinessSubject[] | null>(null);

  useEffect(() => {
    api<{ assignments: Assignment[] }>("/v1/assignments")
      .then((r) => setAssignments(r.assignments))
      .catch(() => setAssignments([]));
    api<{ subjects: ReadinessSubject[] }>("/v1/readiness")
      .then((r) => setReadiness(r.subjects))
      .catch(() => setReadiness([]));
  }, []);

  return (
    <>
      {assignments.length > 0 && (
        <section className="flex flex-col gap-2 anim-rise" aria-labelledby="goals-tasks">
          <h2 id="goals-tasks" className="label">📌 {t("goals.tasks")}</h2>
          {assignments.map((a) => (
            <Link
              key={a.id}
              href={`/learn?title=${encodeURIComponent(a.topic)}&assignment=${a.id}`}
              className="option"
            >
              <span className="text-3xl" aria-hidden="true">📌</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="[overflow-wrap:anywhere]">{a.topic}</span>
                {a.note && <span className="text-sm font-bold text-muted">💬 {a.note}</span>}
              </span>
              <span className="text-2xl text-muted" aria-hidden="true">›</span>
            </Link>
          ))}
        </section>
      )}

      {readiness && (
        <section className="card flex flex-col gap-3 anim-rise" aria-labelledby="goals-ers">
          <h2 id="goals-ers" className="text-lg font-black">🎯 {t("goals.readiness")}</h2>
          {readiness.length === 0 && <p className="text-sm font-bold text-muted">{t("goals.readiness_empty")}</p>}
          {readiness.map((r) => (
            <div key={r.subject_id} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate font-extrabold">{r.subject}</span>
                <span className="shrink-0 text-xl font-black">{r.score === null ? "—" : `${r.score}%`}</span>
              </div>
              {r.score === null ? (
                <p className="text-xs font-bold text-muted">
                  {t("goals.readiness_more", { n: Math.max(0, (r.min_attempts ?? 20) - r.attempts) })}
                </p>
              ) : (
                <Bar value={r.score} />
              )}
              {r.advice.length > 0 && (r.score ?? 0) < 80 && (
                <p className="text-xs font-bold text-muted">💡 {t("goals.advice", { topics: r.advice.map((a) => a.name).join(", ") })}</p>
              )}
            </div>
          ))}
        </section>
      )}
    </>
  );
}
