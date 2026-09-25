"use client";

/* Academic Copilot: загрузка рукописных работ на ИИ-проверку и список проверок. */
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/checks";
import { RequireTeacher } from "@/components/RequireTeacher";
import { Dots, IconButton, Notice, Page } from "@/components/ui";
import { api, ApiError, errorCode } from "@/lib/api";
import { shrinkImage } from "@/lib/image";
import { useT } from "@/lib/i18n";
import type { Journal, WorkCheck } from "@/lib/types";

const MAX_FILES = 40;
const MAX_MB = 10;
const SUBJECTS = ["math", "russian", "uzbek", "english", "physics", "nature", "history", "other"];
const LOCALE: Record<string, string> = { ru: "ru-RU", uz: "uz-Latn-UZ", en: "en-GB" };

type Picked = { file: File; studentId: number };

function UploadForm({ onCreated }: { onCreated: (id: number) => void }) {
  const t = useT();
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("math");
  const [grade, setGrade] = useState("");
  const [maxScore, setMaxScore] = useState("5");
  const [task, setTask] = useState("");
  const [key, setKey] = useState("");
  const [consent, setConsent] = useState(false);
  const [files, setFiles] = useState<Picked[]>([]);
  const [students, setStudents] = useState<{ id: number; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Ученики учителя — для подписи работ (журнал уже отдаёт привязанных учеников)
    api<Journal>("/journal?limit=1")
      .then((j) => setStudents(j.students.map((s) => ({ id: s.id, name: s.name }))))
      .catch(() => setStudents([]));
  }, []);

  const add = (list: FileList | null) => {
    if (!list) return;
    setError(null);
    const next = [...files, ...Array.from(list).map((file) => ({ file, studentId: 0 }))];
    if (next.length > MAX_FILES) setError("too_many_files");
    setFiles(next.slice(0, MAX_FILES));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("title", title.trim());
      form.set("subject", subject);
      if (grade) form.set("grade", grade);
      form.set("max_score", maxScore);
      if (task.trim()) form.set("task_text", task.trim());
      if (key.trim()) form.set("answer_key", key.trim());
      form.set("training_consent", String(consent));
      for (const { file, studentId } of files) {
        // Сжатие на клиенте: фото с телефона 4–8 МБ → ~0.5 МБ, быстрее на 3G. PDF/HEIC — как есть
        const isPhoto = /^image\/(jpeg|png|webp)$/.test(file.type);
        const blob = isPhoto ? await shrinkImage(file) : file;
        if (blob.size > MAX_MB * 1024 * 1024) throw new ApiError(413, "file_too_large");
        form.append("files", blob, file.name);
        form.append("student_ids", String(studentId));
      }
      const r = await api<{ check_id: number }>("/v1/teacher/checks", { method: "POST", form });
      onCreated(r.check_id);
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="card flex flex-col gap-4">
      <h2 className="text-xl font-black">📤 {t("checks.new")}</h2>
      {error && <Notice tone="error">{t(`errors.${error}`, { limit: MAX_FILES, mb: MAX_MB })}</Notice>}
      <label>
        <span className="label">{t("checks.title_label")}</span>
        <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t("checks.title_placeholder")} required maxLength={255} />
      </label>
      <div className="grid grid-cols-3 gap-3">
        <label className="col-span-3 sm:col-span-1">
          <span className="label">{t("learn.subject")}</span>
          <select className="field" value={subject} onChange={(e) => setSubject(e.target.value)}>
            {SUBJECTS.map((s) => (
              <option key={s} value={s}>
                {t(`subjects.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="label">{t("learn.grade")}</span>
          <select className="field" value={grade} onChange={(e) => setGrade(e.target.value)}>
            <option value="">—</option>
            {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </label>
        <label className="col-span-2 sm:col-span-1">
          <span className="label">{t("checks.max_score")}</span>
          <input className="field" type="number" min={1} max={100} value={maxScore} onChange={(e) => setMaxScore(e.target.value)} required />
        </label>
      </div>
      <label>
        <span className="label">{t("checks.task")}</span>
        <textarea className="field min-h-[4.5rem]" value={task} onChange={(e) => setTask(e.target.value)} placeholder={t("checks.task_placeholder")} maxLength={4000} />
      </label>
      <label>
        <span className="label">{t("checks.answer_key")}</span>
        <textarea className="field min-h-[3.5rem]" value={key} onChange={(e) => setKey(e.target.value)} placeholder={t("checks.answer_key_placeholder")} maxLength={4000} />
      </label>

      <div className="flex flex-col gap-2">
        <span className="label">{t("checks.files", { n: files.length, max: MAX_FILES })}</span>
        <input
          ref={input}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/heic,.heic,application/pdf"
          className="hidden"
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
        <button type="button" className="btn btn-soft" onClick={() => input.current?.click()}>
          📷 {t("checks.add_files")}
        </button>
        <p className="text-sm font-semibold text-muted">{t("checks.files_hint", { mb: MAX_MB })}</p>
        {files.length > 0 && (
          <ul className="flex max-h-72 flex-col gap-2 overflow-y-auto">
            {files.map((f, i) => (
              <li key={`${f.file.name}-${i}`} className="flex items-center gap-2 rounded-2xl bg-soft px-3 py-2">
                <span className="min-w-0 flex-1 truncate text-sm font-bold">{f.file.name}</span>
                <select
                  className="max-w-[45%] rounded-xl border-[length:var(--border-w)] border-line bg-surface px-2 py-1.5 text-sm font-bold"
                  value={f.studentId}
                  aria-label={t("checks.student")}
                  onChange={(e) => setFiles((list) => list.map((x, j) => (j === i ? { ...x, studentId: Number(e.target.value) } : x)))}
                >
                  <option value={0}>{t("checks.student_unknown")}</option>
                  {students.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <button type="button" className="px-1 text-lg text-muted" aria-label={t("checks.remove")} onClick={() => setFiles((list) => list.filter((_, j) => j !== i))}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <label className="flex items-start gap-3 text-sm font-semibold">
        <input type="checkbox" className="mt-1 h-5 w-5 accent-[rgb(var(--primary))]" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>{t("checks.training_consent")}</span>
      </label>

      <button className="btn btn-primary" disabled={busy || !title.trim() || files.length === 0}>
        {busy ? <Dots /> : `🤖 ${t("checks.submit", { n: files.length })}`}
      </button>
      <p className="text-center text-xs font-bold text-muted">{t("checks.ai_is_helper")}</p>
    </form>
  );
}

function ChecksView() {
  const t = useT();
  const router = useRouter();
  const [checks, setChecks] = useState<WorkCheck[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<{ checks: WorkCheck[] }>("/v1/teacher/checks")
      .then((r) => setChecks(r.checks))
      .catch((e) => setError(errorCode(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Пока ИИ проверяет — обновляем список сами
  const busy = checks?.some((c) => c.status === "queued" || c.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const id = window.setInterval(load, 4000);
    return () => window.clearInterval(id);
  }, [busy, load]);

  return (
    <Page className="gap-5 lg:max-w-6xl">
      <header className="flex items-center gap-3">
        <IconButton href="/journal" label={t("profile.back")}>‹</IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-black">📝 {t("checks.title")}</h1>
          <p className="text-sm font-bold text-muted">{t("checks.subtitle")}</p>
        </div>
      </header>
      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <UploadForm onCreated={(id) => router.push(`/teacher/checks/${id}`)} />
        <section className="flex flex-col gap-3">
          <h2 className="label">🗂 {t("checks.history")}</h2>
          {checks === null && !error && <Dots />}
          {checks?.length === 0 && <Notice>{t("checks.empty")}</Notice>}
          {checks?.map((c) => {
            const total = Object.values(c.counts ?? {}).reduce((a, b) => a + (b ?? 0), 0);
            const done = (c.counts?.review ?? 0) + (c.counts?.confirmed ?? 0) + (c.counts?.failed ?? 0);
            return (
              <Link key={c.id} href={`/teacher/checks/${c.id}`} className="option flex-col !items-stretch gap-2">
                <span className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate">{c.title}</span>
                  <StatusBadge status={c.status} />
                </span>
                <span className="flex items-center justify-between gap-2 text-sm font-bold text-muted">
                  <span>{new Intl.DateTimeFormat(LOCALE[t.lang], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(c.created_at))}</span>
                  <span>{t("checks.progress", { done, total })}</span>
                </span>
              </Link>
            );
          })}
        </section>
      </div>
    </Page>
  );
}

export default function ChecksPage() {
  return (
    <RequireTeacher>
      <ChecksView />
    </RequireTeacher>
  );
}
