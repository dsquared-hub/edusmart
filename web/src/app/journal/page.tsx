"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Mascot } from "@/components/Mascot";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT, type T } from "@/lib/i18n";
import { subjectIcon } from "@/lib/subjects";
import type { Journal, JournalEntry, JournalStudent } from "@/lib/types";

const LOCALE: Record<string, string> = { ru: "ru-RU", uz: "uz-Latn-UZ", en: "en-GB" };

function dayKey(date: Date) {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

/** «Сегодня», «Вчера» или дата — заголовок группы результатов. */
function dayLabel(date: Date, t: T) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (dayKey(date) === dayKey(today)) return t("journal.today");
  if (dayKey(date) === dayKey(yesterday)) return t("journal.yesterday");
  return new Intl.DateTimeFormat(LOCALE[t.lang], {
    day: "numeric",
    month: "long",
    year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
  }).format(date);
}

function Meter({ value }: { value: number | null }) {
  // Цвет — подсказка, а число рядом — основной сигнал (не полагаемся только на цвет)
  const tone = value === null ? "bg-line" : value >= 80 ? "bg-good" : value >= 50 ? "bg-accent" : "bg-bad";
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
      <div className={`h-full rounded-full ${tone} transition-all duration-700`} style={{ width: `${value ?? 0}%` }} />
    </div>
  );
}

function StudentCard({ student }: { student: JournalStudent }) {
  const t = useT();
  const lastActive = student.last_active_on
    ? new Intl.DateTimeFormat(LOCALE[t.lang], { day: "numeric", month: "short" }).format(
        new Date(`${student.last_active_on}T00:00:00`),
      )
    : "—";
  return (
    <section className="card flex flex-col gap-3 anim-rise" aria-label={student.name}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="min-w-0 truncate text-xl font-black">{student.name}</h2>
        {student.grade && (
          <span className="shrink-0 text-sm font-extrabold text-muted">{t("journal.grade", { grade: student.grade })}</span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-2xl bg-soft px-2 py-2">
          <div className="text-2xl font-black leading-tight">{student.topics_completed}</div>
          <div className="text-xs font-extrabold uppercase tracking-wide text-muted">{t("journal.topics")}</div>
        </div>
        <div className="rounded-2xl bg-soft px-2 py-2">
          <div className="text-2xl font-black leading-tight">{student.topics_week}</div>
          <div className="text-xs font-extrabold uppercase tracking-wide text-muted">{t("journal.week")}</div>
        </div>
        <div className="rounded-2xl bg-soft px-2 py-2">
          <div className="text-2xl font-black leading-tight">🔥 {student.streak}</div>
          <div className="text-xs font-extrabold uppercase tracking-wide text-muted">{t("journal.streak")}</div>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between gap-2 text-sm font-extrabold">
          <span className="text-muted">🎯 {t("journal.accuracy")}</span>
          <span className="text-base">{student.accuracy === null ? "—" : `${student.accuracy}%`}</span>
        </div>
        <Meter value={student.accuracy} />
      </div>

      {student.weak.length > 0 && (
        <div className="text-sm font-bold">
          <span className="text-muted">{t("journal.weak")}: </span>
          {student.weak.map((w) => t("journal.weak_item", { title: w.title, n: w.mistakes })).join(", ")}
        </div>
      )}
      <div className="text-sm font-bold text-muted">
        ⭐ {student.points} · {t("journal.last_active", { date: lastActive })}
      </div>
      <a href={`/family/${student.id}`} className="btn btn-soft !min-h-[2.75rem] text-base">
        📊 {t("report.open")}
      </a>
    </section>
  );
}

function EntryRow({ entry, showName }: { entry: JournalEntry; showName: boolean }) {
  const t = useT();
  const time = new Intl.DateTimeFormat(LOCALE[t.lang], { hour: "2-digit", minute: "2-digit" }).format(
    new Date(entry.completed_at),
  );
  const perfect = entry.questions > 0 && entry.first_try === entry.questions;
  return (
    <li className="flex gap-3 rounded-2xl border-[length:var(--border-w)] border-line bg-surface px-4 py-3">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-soft text-2xl" aria-hidden="true">
        {subjectIcon(entry.subject)}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="min-w-0 font-extrabold [overflow-wrap:anywhere]">{entry.title}</span>
          <span className="shrink-0 text-sm font-bold text-muted">{time}</span>
        </div>
        {showName && <span className="text-sm font-bold text-muted">👤 {entry.student_name}</span>}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm font-extrabold">
          <span className={perfect ? "text-good" : ""}>
            ✔️ {t("journal.first_try", { n: entry.first_try, total: entry.questions })}
          </span>
          <span className={entry.mistakes > 0 ? "text-bad" : "text-muted"}>
            ❌ {t("journal.mistakes", { n: entry.mistakes })}
          </span>
          <span>⭐ +{entry.points}</span>
          <span className="text-muted">{entry.source === "bot" ? `✈️ ${t("journal.in_bot")}` : `🌐 ${t("journal.on_site")}`}</span>
        </div>
      </div>
    </li>
  );
}

function JournalView() {
  const t = useT();
  const { me } = useAuth();
  const [studentId, setStudentId] = useState<number | null>(null);
  const [data, setData] = useState<Journal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async (id: number | null, before?: number) => {
    const params = new URLSearchParams();
    if (id !== null) params.set("student_id", String(id));
    if (before !== undefined) params.set("before", String(before));
    const query = params.toString();
    return api<Journal>(`/journal${query ? `?${query}` : ""}`);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    load(studentId)
      .then((journal) => !cancelled && setData(journal))
      .catch((e) => !cancelled && setError(errorCode(e)));
    return () => {
      cancelled = true;
    };
  }, [studentId, load]);

  // Ученики для фильтра — из общего журнала, чтобы список не «схлопывался» при выборе одного
  const [allStudents, setAllStudents] = useState<JournalStudent[]>([]);
  useEffect(() => {
    if (data && studentId === null) setAllStudents(data.students);
  }, [data, studentId]);

  const groups = useMemo(() => {
    const result: { key: string; label: string; entries: JournalEntry[] }[] = [];
    for (const entry of data?.entries ?? []) {
      const date = new Date(entry.completed_at);
      const key = dayKey(date);
      const last = result[result.length - 1];
      if (last && last.key === key) last.entries.push(entry);
      else result.push({ key, label: dayLabel(date, t), entries: [entry] });
    }
    return result;
  }, [data, t]);

  const loadMore = async () => {
    if (!data || data.entries.length === 0) return;
    setLoadingMore(true);
    try {
      const more = await load(studentId, data.entries[data.entries.length - 1].topic_id);
      setData({ ...data, entries: [...data.entries, ...more.entries], has_more: more.has_more });
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setLoadingMore(false);
    }
  };

  if (!data && !error) return <Splash />;

  const shown = data?.students ?? [];
  const multiple = allStudents.length > 1;

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3 anim-rise">
        <Mascot size={56} />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-black leading-tight">📒 {t("journal.title")}</h1>
          <p className="text-sm font-bold text-muted">{t("journal.subtitle")}</p>
        </div>
        {me?.role === "teacher" && (
          <>
            <IconButton href="/teacher" label={t("panel.title")}>📊</IconButton>
            <IconButton href="/teacher/checks" label={t("checks.journal_link")}>📝</IconButton>
            <IconButton href="/teacher/materials" label={t("materials.journal_link")}>🧑‍🏫</IconButton>
          </>
        )}
        {me?.role === "parent" && (
          <IconButton href="/family" label={t("family.title")}>👨‍👩‍👧</IconButton>
        )}
        <IconButton href="/support" label={t("support.title")}>💬</IconButton>
        <IconButton href="/profile" label={t("profile.title")}>⚙️</IconButton>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {data && allStudents.length === 0 && studentId === null && (
        <section className="card flex flex-col items-center gap-3 text-center">
          <Mascot size={80} />
          <h2 className="text-xl font-black">{t("journal.no_students_title")}</h2>
          <p className="font-semibold text-muted">{t("journal.no_students_text")}</p>
        </section>
      )}

      {multiple && (
        <nav className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1" aria-label={t("journal.filter")}>
          <button type="button" className="chip" aria-pressed={studentId === null} onClick={() => setStudentId(null)}>
            👥 {t("journal.all")}
          </button>
          {allStudents.map((s) => (
            <button
              key={s.id}
              type="button"
              className="chip"
              aria-pressed={studentId === s.id}
              onClick={() => setStudentId(s.id)}
            >
              {s.name}
            </button>
          ))}
        </nav>
      )}

      {shown.map((s) => (
        <StudentCard key={s.id} student={s} />
      ))}

      {data && shown.length > 0 && (
        <section className="flex flex-col gap-3" aria-labelledby="journal-results">
          <h2 id="journal-results" className="label">
            🏆 {t("journal.results")}
          </h2>
          {groups.length === 0 && <Notice>{t("journal.no_entries")}</Notice>}
          {groups.map((group) => (
            <div key={group.key} className="flex flex-col gap-2">
              <h3 className="text-sm font-extrabold text-muted">{group.label}</h3>
              <ul className="flex flex-col gap-2">
                {group.entries.map((entry) => (
                  <EntryRow key={entry.topic_id} entry={entry} showName={multiple && studentId === null} />
                ))}
              </ul>
            </div>
          ))}
          {data.has_more && (
            <button type="button" className="btn btn-soft" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? <Dots /> : t("journal.more")}
            </button>
          )}
        </section>
      )}
    </Page>
  );
}

export default function JournalPage() {
  const t = useT();
  const router = useRouter();
  const { status, me } = useAuth();

  useEffect(() => {
    if (status === "guest") router.replace("/login?next=/journal");
    else if (status === "authed" && me?.role === "student") router.replace("/");
  }, [status, me, router]);

  if (status !== "authed" || !me || me.role === "student") return <Splash />;

  if (me.role !== "parent" && me.role !== "teacher") {
    return (
      <Page className="justify-center">
        <div className="card flex flex-col items-center gap-4 text-center">
          <Mascot size={96} />
          <h1 className="text-2xl font-black">{t("journal.no_role_title")}</h1>
          <p className="text-muted">{t("journal.no_role_text")}</p>
        </div>
      </Page>
    );
  }
  return <JournalView />;
}
