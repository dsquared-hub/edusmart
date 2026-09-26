"use client";

/* Панель учителя (Модуль 5, п. 4.3): тепловая карта «ученики × темы», кому нужна помощь,
   частые вопросы класса к ИИ, очередь проверки работ и задания классу. */
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { RequireTeacher } from "@/components/RequireTeacher";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";

type Panel = {
  students: { id: number; name: string; grade: number | null }[];
  heatmap: { topics: { id: number; name: string; subject: string }[]; cells: Record<string, Record<string, number>> };
  needs_help: { student_id: number; name: string; before: number; after: number; drop: number }[];
  questions: { topic_id: number | null; name: string; students: number; asked: number }[];
};
type CTopic = { id: number; name: string; subject: string; grade: number };

function cellClass(value: number | undefined) {
  if (value === undefined) return "bg-line/40 text-muted";
  if (value >= 80) return "bg-good/25";
  if (value >= 50) return "bg-accent/35";
  return "bg-bad/25";
}

function AssignForm({ students, onDone }: { students: Panel["students"]; onDone: (n: number) => void }) {
  const t = useT();
  const [topics, setTopics] = useState<CTopic[]>([]);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ topics: CTopic[] }>("/v1/curriculum/topics").then((r) => setTopics(r.topics)).catch(() => setTopics([]));
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!topicId) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ assigned: number }>("/v1/teacher/assignments", {
        method: "POST",
        json: { topic_id: topicId, student_ids: picked.length ? picked : null, note: note.trim() || null },
      });
      onDone(r.assigned);
      setNote("");
      setPicked([]);
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="card flex flex-col gap-3">
      <h2 className="text-xl font-black">📌 {t("panel.assign")}</h2>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      <select className="field" value={topicId ?? ""} onChange={(e) => setTopicId(Number(e.target.value) || null)} required aria-label={t("materials.topic")}>
        <option value="">{t("panel.pick_topic")}</option>
        {topics.map((tp) => (
          <option key={tp.id} value={tp.id}>
            {tp.grade} · {tp.subject} — {tp.name}
          </option>
        ))}
      </select>
      <div className="flex flex-wrap gap-2" aria-label={t("panel.who")}>
        <button type="button" className="chip" aria-pressed={picked.length === 0} onClick={() => setPicked([])}>
          👥 {t("panel.whole_class")}
        </button>
        {students.map((s) => (
          <button
            key={s.id}
            type="button"
            className="chip"
            aria-pressed={picked.includes(s.id)}
            onClick={() => setPicked((p) => (p.includes(s.id) ? p.filter((x) => x !== s.id) : [...p, s.id]))}
          >
            {s.name}
          </button>
        ))}
      </div>
      <input className="field" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={t("panel.note")} />
      <button className="btn btn-primary" disabled={busy || !topicId || students.length === 0}>
        {busy ? <Dots /> : t("panel.send", { n: picked.length || students.length })}
      </button>
    </form>
  );
}

function PanelView() {
  const t = useT();
  const [panel, setPanel] = useState<Panel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<number | null>(null);

  useEffect(() => {
    api<Panel>("/v1/teacher/panel").then(setPanel).catch((e) => setError(errorCode(e)));
  }, []);

  if (!panel && !error) return <Splash />;

  return (
    <Page className="gap-5 lg:max-w-6xl">
      <header className="flex items-center gap-3">
        <h1 className="flex-1 text-2xl font-black">👩‍🏫 {t("panel.title")}</h1>
        <IconButton href="/journal" label={t("journal.title")}>📒</IconButton>
        <IconButton href="/teacher/checks" label={t("checks.title")}>📝</IconButton>
        <IconButton href="/teacher/materials" label={t("materials.title")}>🧑‍🏫</IconButton>
        <IconButton href="/support" label={t("support.title")}>💬</IconButton>
        <IconButton href="/profile" label={t("profile.title")}>⚙️</IconButton>
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      {sent !== null && <Notice>✅ {t("panel.sent", { n: sent })}</Notice>}

      {panel && panel.students.length === 0 && <Notice>{t("journal.no_students_text")}</Notice>}

      {panel && panel.students.length > 0 && (
        <>
          <section className="card flex flex-col gap-3">
            <h2 className="text-xl font-black">🗺 {t("panel.heatmap")}</h2>
            <p className="text-sm font-semibold text-muted">{t("report.legend")}</p>
            {panel.heatmap.topics.length === 0 ? (
              <Notice>{t("report.no_data")}</Notice>
            ) : (
              <div className="overflow-x-auto">
                <table className="border-separate border-spacing-1 text-sm">
                  <thead>
                    <tr>
                      <th className="sticky left-0 bg-surface" />
                      {panel.heatmap.topics.map((tp) => (
                        <th key={tp.id} className="max-w-[7rem] px-1 text-left align-bottom text-xs font-extrabold" title={tp.subject}>
                          {tp.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {panel.students.map((s) => (
                      <tr key={s.id}>
                        <th scope="row" className="sticky left-0 whitespace-nowrap bg-surface pr-2 text-left font-extrabold">
                          <Link href={`/family/${s.id}`} className="hover:underline">{s.name}</Link>
                        </th>
                        {panel.heatmap.topics.map((tp) => {
                          const v = panel.heatmap.cells[String(s.id)]?.[String(tp.id)];
                          return (
                            <td key={tp.id} className={`h-10 min-w-[3.25rem] rounded-lg text-center font-black ${cellClass(v)}`}>
                              {v === undefined ? "—" : `${v}%`}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div className="grid gap-5 lg:grid-cols-2">
            <section className="card flex flex-col gap-3">
              <h2 className="text-xl font-black">🆘 {t("panel.help")}</h2>
              <p className="text-sm font-semibold text-muted">{t("panel.help_hint")}</p>
              {panel.needs_help.length === 0 && <Notice>{t("panel.help_none")}</Notice>}
              {panel.needs_help.map((h) => (
                <Link key={h.student_id} href={`/family/${h.student_id}`} className="option !min-h-0 justify-between !py-2.5">
                  <span className="truncate">{h.name}</span>
                  <span className="shrink-0 text-sm font-black text-bad">
                    {h.before}% → {h.after}% (−{h.drop})
                  </span>
                </Link>
              ))}
            </section>

            <section className="card flex flex-col gap-3">
              <h2 className="text-xl font-black">❓ {t("panel.questions")}</h2>
              {panel.questions.length === 0 && <Notice>{t("report.no_data")}</Notice>}
              {panel.questions.map((q, i) => (
                <div key={`${q.topic_id}-${i}`} className="flex items-center justify-between gap-2 rounded-2xl bg-soft px-3 py-2.5">
                  <span className="min-w-0 truncate font-extrabold">{q.name}</span>
                  <span className="shrink-0 text-sm font-bold text-muted">{t("panel.asked", { n: q.students })}</span>
                </div>
              ))}
            </section>
          </div>

          <AssignForm students={panel.students} onDone={setSent} />
        </>
      )}
    </Page>
  );
}

export default function TeacherPanelPage() {
  return (
    <RequireTeacher>
      <PanelView />
    </RequireTeacher>
  );
}
