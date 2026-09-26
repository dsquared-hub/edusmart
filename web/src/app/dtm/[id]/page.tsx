"use client";

/* Экзамен ДТМ: таймер (время — по серверу), навигатор по 90 вопросам, ответы сохраняются
   сразу и меняются до завершения. После — баллы по блокам и разбор ошибок, в том числе
   с сократовским тьютором (он не даёт ответ, а ведёт к нему вопросами). */
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Dots, Notice, Page, Splash } from "@/components/ui";
import { MathText } from "@/components/MathText";
import { api, errorCode } from "@/lib/api";
import { useT, type T } from "@/lib/i18n";
import type { DtmQuestion, DtmTest, TutorDialog } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D"];

function clock(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function blockName(block: string, test: DtmTest, t: T, subject: string, names: Record<string, string>) {
  if (block === "spec1") return `🥇 ${test.spec1.name}`;
  if (block === "spec2") return `🥈 ${test.spec2.name}`;
  return `📘 ${names[subject] ?? t(`dtm.subject.${subject}`)}`;
}

function Results({ test }: { test: DtmTest }) {
  const t = useT();
  const router = useRouter();
  const [onlyWrong, setOnlyWrong] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const names = useMemo(() => ({ [test.spec1.code]: test.spec1.name, [test.spec2.code]: test.spec2.name }), [test]);
  const shown = test.questions.filter((q) => !onlyWrong || q.answer !== q.correct);

  const withTutor = async (q: DtmQuestion) => {
    setBusy(q.n);
    setError(null);
    try {
      const text = `${q.question}\n${q.options.map((o, i) => `${LETTERS[i]}) ${o}`).join("  ")}`.slice(0, 500);
      const form = new FormData();
      form.set("text", text);
      const dialog = await api<TutorDialog>("/tutor", { method: "POST", form });
      router.push(`/tutor/${dialog.id}`);
    } catch (e) {
      setError(errorCode(e));
      setBusy(null);
    }
  };

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <Link href="/dtm" className="grid h-11 w-11 place-items-center rounded-2xl bg-surface text-2xl font-black" aria-label={t("profile.back")}>‹</Link>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">📊 {t("dtm.result")}</h1>
      </header>

      <section className="card flex flex-col items-center gap-1 text-center anim-pop">
        <span className="text-5xl font-black text-primary">{test.score}</span>
        <span className="font-extrabold text-muted">{t("dtm.of_max", { max: test.max_score })}</span>
      </section>

      <section className="card flex flex-col gap-2">
        {Object.entries(test.results ?? {}).map(([block, r]) => (
          <div key={block} className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate font-extrabold">{blockName(block, test, t, r.subject, names)}</span>
            <span className="shrink-0 text-sm font-black">
              {r.correct}/{r.total} · {r.points} {t("dtm.points")}
            </span>
          </div>
        ))}
      </section>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <div className="flex gap-2">
        <button type="button" className="chip" aria-pressed={onlyWrong} onClick={() => setOnlyWrong(true)}>❌ {t("dtm.only_wrong")}</button>
        <button type="button" className="chip" aria-pressed={!onlyWrong} onClick={() => setOnlyWrong(false)}>📋 {t("dtm.all_questions")}</button>
      </div>

      <ol className="flex flex-col gap-3">
        {shown.map((q) => (
          <li key={q.n} className="card flex flex-col gap-2">
            <span className="text-xs font-extrabold text-muted">#{q.n + 1} · {blockName(q.block, test, t, q.subject, names)}</span>
            <p className="font-black [overflow-wrap:anywhere]"><MathText text={q.question} /></p>
            {q.options.map((o, i) => (
              <div key={i} className="option !min-h-[2.75rem] !text-base" data-state={i === q.correct ? "correct" : i === q.answer ? "wrong" : undefined}>
                <span className="option-letter">{LETTERS[i]}</span>
                <span className="min-w-0 flex-1"><MathText text={o} /></span>
              </div>
            ))}
            {q.answer === null && <p className="text-sm font-bold text-muted">— {t("dtm.no_answer")}</p>}
            {q.explanation && <p className="text-sm font-bold">💡 <MathText text={q.explanation} /></p>}
            {q.answer !== q.correct && (
              <button type="button" className="btn btn-soft !min-h-[2.75rem] text-base" onClick={() => withTutor(q)} disabled={busy !== null}>
                {busy === q.n ? <Dots /> : `🦏 ${t("dtm.with_tutor")}`}
              </button>
            )}
          </li>
        ))}
      </ol>
      <Link href="/dtm" className="btn btn-primary">🎓 {t("dtm.title")}</Link>
    </Page>
  );
}

function Exam({ initial }: { initial: DtmTest }) {
  const t = useT();
  const [test, setTest] = useState(initial);
  const [current, setCurrent] = useState(() => Math.max(0, initial.questions.findIndex((q) => q.answer === null)));
  const [left, setLeft] = useState(initial.seconds_left);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Конец — от оставшихся секунд сервера, а не от часов устройства
  const [endAt] = useState(() => Date.now() + initial.seconds_left * 1000);

  const finish = useCallback(async () => {
    setFinishing(true);
    try {
      setTest(await api<DtmTest>(`/dtm/${initial.id}/finish`, { method: "POST" }));
    } catch (e) {
      setError(errorCode(e));
      setFinishing(false);
    }
  }, [initial.id]);

  useEffect(() => {
    const id = setInterval(() => {
      const s = Math.max(0, Math.round((endAt - Date.now()) / 1000));
      setLeft(s);
      if (s === 0) {
        clearInterval(id);
        void finish();
      }
    }, 1000);
    return () => clearInterval(id);
  }, [endAt, finish]);

  if (test.status === "finished") return <Results test={test} />;

  const q = test.questions[current];
  const answered = test.questions.filter((x) => x.answer !== null).length;

  const choose = async (option: number) => {
    const next = q.answer === option ? null : option; // повторное нажатие — снять ответ
    const before = test;
    setTest({ ...test, questions: test.questions.map((x) => (x.n === q.n ? { ...x, answer: next } : x)) });
    try {
      await api(`/dtm/${test.id}/answer`, { method: "PUT", json: { slot: q.n, option: next } });
    } catch (e) {
      setTest(before);
      setError(errorCode(e));
    }
  };

  const askFinish = () => {
    const rest = test.total - answered;
    if (window.confirm(rest > 0 ? t("dtm.confirm_unanswered", { n: rest }) : t("dtm.confirm"))) void finish();
  };

  return (
    <Page className="gap-4 lg:max-w-3xl">
      <header className="sticky top-0 z-10 -mx-4 flex items-center gap-3 bg-bg px-4 py-2">
        <Link href="/dtm" className="grid h-11 w-11 place-items-center rounded-2xl bg-surface text-2xl font-black" aria-label={t("profile.back")}>‹</Link>
        <span className={`font-black tabular-nums ${left < 600 ? "text-bad" : ""}`} aria-label={t("dtm.time_left")}>⏱ {clock(left)}</span>
        <span className="min-w-0 flex-1 truncate text-right text-sm font-extrabold text-muted">
          {t("dtm.answered", { n: answered, total: test.total })}
        </span>
        <button type="button" className="btn btn-primary !min-h-[2.5rem] !w-auto px-4 text-base" onClick={askFinish} disabled={finishing}>
          {finishing ? <Dots /> : t("dtm.finish")}
        </button>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <nav className="grid grid-cols-10 gap-1" aria-label={t("dtm.navigator")}>
        {test.questions.map((x) => (
          <button
            key={x.n}
            type="button"
            onClick={() => setCurrent(x.n)}
            aria-current={x.n === current ? "true" : undefined}
            aria-label={`${x.n + 1}`}
            className={`h-8 rounded-lg text-xs font-black ${
              x.n === current ? "bg-primary text-on-primary" : x.answer !== null ? "bg-good/30" : "bg-soft text-muted"
            } ${x.n === 30 || x.n === 60 ? "col-start-1" : ""}`}
          >
            {x.n + 1}
          </button>
        ))}
      </nav>

      <section className="card flex flex-col gap-3" key={q.n}>
        <span className="text-xs font-extrabold text-muted">
          #{q.n + 1} · {blockName(q.block, test, t, q.subject, { [test.spec1.code]: test.spec1.name, [test.spec2.code]: test.spec2.name })}
        </span>
        <p className="text-lg font-black [overflow-wrap:anywhere]"><MathText text={q.question} /></p>
        {q.options.map((o, i) => (
          <button
            key={i}
            type="button"
            className={`option ${q.answer === i ? "!border-primary !bg-primary/10" : ""}`}
            aria-pressed={q.answer === i}
            onClick={() => choose(i)}
          >
            <span className="option-letter">{LETTERS[i]}</span>
            <span className="min-w-0 flex-1"><MathText text={o} /></span>
          </button>
        ))}
      </section>

      <div className="flex gap-2">
        <button type="button" className="btn btn-soft flex-1" onClick={() => setCurrent((c) => Math.max(0, c - 1))} disabled={current === 0}>
          ‹ {t("stories.prev")}
        </button>
        <button
          type="button"
          className="btn btn-soft flex-1"
          onClick={() => setCurrent((c) => Math.min(test.total - 1, c + 1))}
          disabled={current === test.total - 1}
        >
          {t("stories.next")} ›
        </button>
      </div>
    </Page>
  );
}

function ExamPage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [test, setTest] = useState<DtmTest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isInteger(id) && id > 0) api<DtmTest>(`/dtm/${id}`).then(setTest).catch((e) => setError(errorCode(e)));
  }, [id]);

  if (error)
    return (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/dtm" className="btn btn-soft">‹ {t("dtm.title")}</Link>
      </Page>
    );
  if (!test) return <Splash />;
  return test.status === "finished" ? <Results test={test} /> : <Exam initial={test} />;
}

export default function DtmExamPage() {
  return (
    <RequireStudent>
      <ExamPage />
    </RequireStudent>
  );
}
