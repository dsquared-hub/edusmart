"use client";

/* Отчёт родителю (Модуль 4, п. 2.3): итог вечернего теста, светофор тем, динамика,
   аккуратность письменных работ, Exam Readiness Score с советом, задание ребёнку. */
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

type Light = "green" | "yellow" | "red";
type Report = {
  student: { id: number; name: string; grade: number | null; streak: number; evening_time: string };
  lights: { topic_id: number; topic: string; subject: string; accuracy: number | null; light: Light | null }[];
  week: { date: string; answers: number; correct: number }[];
  month: { date: string; answers: number; correct: number }[];
  neatness: number | null;
  readiness: {
    subject_id: number;
    subject: string;
    score: number | null;
    components: Partial<Record<"M" | "S" | "V" | "R", number>>;
    attempts: number;
    min_attempts: number | null;
    advice: { id: number; name: string }[];
    history: { score: number; at: string }[];
  }[];
  last_evening: { date: string; topics_understood: number; topics_total: number; weak_topic: string | null; score: number; total: number } | null;
};

const LIGHT: Record<Light, { dot: string; icon: string }> = {
  green: { dot: "bg-good", icon: "🟢" },
  yellow: { dot: "bg-accent", icon: "🟡" },
  red: { dot: "bg-bad", icon: "🔴" },
};
const TIMES = ["17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00", "21:30"];

/** Столбики «ответы / верные» по дням — без библиотек, в цветах темы. */
function Bars({ days }: { days: Report["week"] }) {
  const t = useT();
  const max = Math.max(1, ...days.map((d) => d.answers));
  const w = 100 / days.length;
  return (
    <svg viewBox="0 0 100 44" className="h-32 w-full" role="img" aria-label={t("report.activity")} preserveAspectRatio="none">
      {days.map((d, i) => {
        const h = (d.answers / max) * 40;
        const hc = (d.correct / max) * 40;
        return (
          <g key={d.date}>
            <rect x={i * w + w * 0.15} y={42 - h} width={w * 0.7} height={h} rx={0.8} style={{ fill: "rgb(var(--line))" }} />
            <rect x={i * w + w * 0.15} y={42 - hc} width={w * 0.7} height={hc} rx={0.8} style={{ fill: "rgb(var(--good))" }} />
          </g>
        );
      })}
    </svg>
  );
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const step = 100 / (points.length - 1);
  const d = points.map((p, i) => `${i * step},${30 - (p / 100) * 28}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" className="h-10 w-full" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={d} fill="none" strokeWidth={2} vectorEffect="non-scaling-stroke" style={{ stroke: "rgb(var(--primary))" }} />
    </svg>
  );
}

function ReportView({ id }: { id: number }) {
  const t = useT();
  const { me } = useAuth();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<"week" | "month">("week");
  const [sent, setSent] = useState<Record<number, boolean>>({});
  const [savingTime, setSavingTime] = useState(false);

  const load = useCallback(() => {
    api<Report>(`/v1/family/report?student_id=${id}`)
      .then(setReport)
      .catch((e) => setError(errorCode(e)));
  }, [id]);
  useEffect(load, [load]);

  const assign = async (topicId: number) => {
    try {
      await api("/v1/assignments", { method: "POST", json: { student_id: id, topic_id: topicId } });
      setSent((s) => ({ ...s, [topicId]: true }));
    } catch (e) {
      setError(errorCode(e));
    }
  };

  const setTime = async (time: string) => {
    setSavingTime(true);
    try {
      await api("/v1/family/evening-time", { method: "PUT", json: { student_id: id, time } });
      setReport((r) => (r ? { ...r, student: { ...r.student, evening_time: time } } : r));
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setSavingTime(false);
    }
  };

  if (!report && !error) return <Splash />;
  const days = report ? report[range] : [];

  return (
    <Page className="gap-5 lg:max-w-4xl">
      <header className="flex items-center gap-3">
        <IconButton href="/journal" label={t("profile.back")}>‹</IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-black">📊 {report?.student.name ?? t("report.title")}</h1>
          {report && (
            <p className="text-sm font-bold text-muted">
              {report.student.grade ? t("journal.grade", { grade: report.student.grade }) + " · " : ""}🔥 {report.student.streak}
            </p>
          )}
        </div>
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {report && (
        <>
          {report.last_evening && (
            <section className="card flex flex-col gap-1">
              <div className="label">🌙 {t("report.last_evening", { date: report.last_evening.date })}</div>
              <div className="text-xl font-black">
                {t("report.understood", { n: report.last_evening.topics_understood, total: report.last_evening.topics_total })}
              </div>
              {report.last_evening.weak_topic && <div className="font-bold text-muted">{t("report.weak", { topic: report.last_evening.weak_topic })}</div>}
            </section>
          )}

          <section className="card flex flex-col gap-4">
            <h2 className="text-xl font-black">🎯 {t("report.readiness")}</h2>
            {report.readiness.length === 0 && <Notice>{t("report.no_data")}</Notice>}
            {report.readiness.map((r) => (
              <div key={r.subject_id} className="flex flex-col gap-2 rounded-2xl bg-soft p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate font-black">{r.subject}</span>
                  <span className="text-3xl font-black">{r.score === null ? "—" : `${r.score}%`}</span>
                </div>
                {r.score === null ? (
                  <p className="text-sm font-bold text-muted">{t("report.not_enough", { n: r.attempts, min: r.min_attempts ?? 20 })}</p>
                ) : (
                  <>
                    <div className="grid grid-cols-4 gap-2 text-center text-xs font-extrabold">
                      {(["M", "S", "V", "R"] as const).map((k) => (
                        <div key={k} className="rounded-xl bg-surface px-1 py-2">
                          <div className="text-base">{Math.round((r.components[k] ?? 0) * 100)}%</div>
                          <div className="text-muted">{t(`report.c_${k}`)}</div>
                        </div>
                      ))}
                    </div>
                    <Sparkline points={r.history.map((h) => h.score)} />
                  </>
                )}
                {r.advice.length > 0 && (r.score ?? 0) < 80 && (
                  <p className="text-sm font-bold">💡 {t("report.advice", { topics: r.advice.map((a) => a.name).join(", ") })}</p>
                )}
              </div>
            ))}
          </section>

          <section className="card flex flex-col gap-3">
            <h2 className="text-xl font-black">🚦 {t("report.topics")}</h2>
            <p className="text-sm font-semibold text-muted">{t("report.legend")}</p>
            {report.lights.length === 0 && <Notice>{t("report.no_data")}</Notice>}
            <ul className="flex flex-col gap-2">
              {report.lights.map((l) => (
                <li key={l.topic_id} className="flex items-center gap-3 rounded-2xl bg-soft px-3 py-2.5">
                  <span className="text-lg" aria-hidden="true">{l.light ? LIGHT[l.light].icon : "⚪"}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-extrabold">{l.topic}</span>
                    <span className="block truncate text-xs font-bold text-muted">{l.subject}</span>
                  </span>
                  <span className="font-black tabular-nums">{l.accuracy ?? "—"}%</span>
                  {me?.id !== id && l.light && l.light !== "green" && (
                    <button className="chip !min-h-[2.25rem] !px-3 text-sm" disabled={sent[l.topic_id]} onClick={() => assign(l.topic_id)}>
                      {sent[l.topic_id] ? `✓ ${t("report.sent")}` : `📌 ${t("report.send_task")}`}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="card flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-xl font-black">📈 {t("report.activity")}</h2>
              <div className="flex gap-2">
                {(["week", "month"] as const).map((r) => (
                  <button key={r} className="chip !min-h-[2.25rem]" aria-pressed={range === r} onClick={() => setRange(r)}>
                    {t(`report.${r}`)}
                  </button>
                ))}
              </div>
            </div>
            <Bars days={days} />
            <p className="text-sm font-bold text-muted">
              {t("report.totals", { answers: days.reduce((a, d) => a + d.answers, 0), correct: days.reduce((a, d) => a + d.correct, 0) })}
            </p>
          </section>

          <section className="grid gap-3 sm:grid-cols-2">
            <div className="card">
              <div className="label">✍️ {t("report.neatness")}</div>
              <div className="text-3xl font-black">{report.neatness === null ? "—" : `${report.neatness}%`}</div>
              <p className="text-sm font-semibold text-muted">{t("report.neatness_hint")}</p>
            </div>
            {me?.role === "parent" && (
              <div className="card">
                <label>
                  <span className="label">🔔 {t("report.evening_time")}</span>
                  <select className="field" value={report.student.evening_time} disabled={savingTime} onChange={(e) => setTime(e.target.value)}>
                    {TIMES.map((time) => (
                      <option key={time} value={time}>
                        {time}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="mt-2 text-sm font-semibold text-muted">{savingTime ? <Dots /> : t("report.evening_time_hint")}</p>
              </div>
            )}
          </section>
        </>
      )}
    </Page>
  );
}

export default function FamilyReportPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { status } = useAuth();
  useEffect(() => {
    if (status === "guest") router.replace(`/login?next=/family/${params.id}`);
  }, [status, router, params.id]);
  if (status !== "authed") return <Splash />;
  return <ReportView id={Number(params.id)} />;
}
