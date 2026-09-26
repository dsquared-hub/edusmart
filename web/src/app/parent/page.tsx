"use client";

/* Кабинет родителя: только успехи своих детей — сводка по каждому, вечерний тест
   сегодня и переходы к подробному отчёту и журналу. Уроки родителю недоступны. */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Mascot } from "@/components/Mascot";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT, type T } from "@/lib/i18n";
import type { CabinetChild, ParentCabinet, PublicConfig, StudyState } from "@/lib/types";

const LOCALE: Record<string, string> = { ru: "ru-RU", uz: "uz-Latn-UZ", en: "en-GB" };

function lastActive(day: string | null, t: T) {
  if (!day) return t("cabinet.never");
  const date = new Date(`${day}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today.getTime() - date.getTime()) / 86_400_000);
  if (diff === 0) return t("journal.today");
  if (diff === 1) return t("journal.yesterday");
  return new Intl.DateTimeFormat(LOCALE[t.lang], { day: "numeric", month: "short" }).format(date);
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="rounded-2xl bg-soft px-2 py-2 text-center">
      <div className="text-2xl font-black leading-tight">{value}</div>
      <div className="text-xs font-extrabold uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

const STATE: Record<StudyState, { icon: string; tone: string }> = {
  done: { icon: "🟢", tone: "bg-good/20" },
  partial: { icon: "🟡", tone: "bg-accent/20" },
  missed: { icon: "🔴", tone: "bg-bad/15" },
  today: { icon: "⏳", tone: "bg-soft" },
  none: { icon: "⚪", tone: "bg-soft opacity-60" },
};

/** Неделя по дням: 🟢 прошёл тест · 🟡 занимался · 🔴 пропустил. Подпись — день недели. */
function WeekStrip({ week }: { week: CabinetChild["week"] }) {
  const t = useT();
  const fmt = new Intl.DateTimeFormat(LOCALE[t.lang], { weekday: "short" });
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-7 gap-1">
        {week.map((d) => (
          <div
            key={d.date}
            className={`flex flex-col items-center rounded-xl py-1.5 ${STATE[d.state].tone}`}
            title={t(`cabinet.state_${d.state}`)}
          >
            <span className="text-lg leading-none" aria-hidden="true">{STATE[d.state].icon}</span>
            <span className="mt-1 text-[0.7rem] font-extrabold uppercase text-muted">{fmt.format(new Date(`${d.date}T00:00:00`))}</span>
            <span className="sr-only">{t(`cabinet.state_${d.state}`)}</span>
          </div>
        ))}
      </div>
      <p className="text-xs font-bold text-muted">{t("cabinet.week_legend")}</p>
    </div>
  );
}

function ReadinessBars({ items }: { items: CabinetChild["readiness"] }) {
  const t = useT();
  const shown = items.filter((r) => r.score !== null);
  if (shown.length === 0) return <p className="text-sm font-bold text-muted">🎯 {t("cabinet.readiness_empty")}</p>;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-extrabold text-muted">🎯 {t("cabinet.readiness")}</span>
      {shown.map((r) => (
        <div key={r.subject} className="flex flex-col gap-1">
          <div className="flex justify-between gap-2 text-sm font-extrabold">
            <span className="min-w-0 truncate">{r.subject}</span>
            <span>{r.score}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <div
              className={`h-full rounded-full ${r.score! >= 80 ? "bg-good" : r.score! >= 50 ? "bg-accent" : "bg-bad"}`}
              style={{ width: `${Math.max(3, r.score!)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function ChildCard({ child }: { child: CabinetChild }) {
  const t = useT();
  const evening = child.evening;
  const eveningText =
    evening === null
      ? t("cabinet.evening_none")
      : evening.status === "finished"
        ? t("cabinet.evening_done", { score: evening.score, total: evening.total })
        : t("cabinet.evening_active");
  return (
    <section className="card flex flex-col gap-3 anim-rise" aria-label={child.name}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="min-w-0 truncate text-xl font-black">👤 {child.name}</h2>
        {child.grade && (
          <span className="shrink-0 text-sm font-extrabold text-muted">{t("journal.grade", { grade: child.grade })}</span>
        )}
      </div>
      <div className="grid grid-cols-4 gap-2">
        <Stat value={child.points} label={t("home.points")} />
        <Stat value={`🔥${child.streak}`} label={t("journal.streak")} />
        <Stat value={child.topics_week} label={t("journal.week")} />
        <Stat value={child.accuracy === null ? "—" : `${child.accuracy}%`} label={t("cabinet.accuracy")} />
      </div>
      {child.week.length > 0 && <WeekStrip week={child.week} />}
      <ReadinessBars items={child.readiness} />
      <p className={`rounded-2xl px-3 py-2 text-sm font-extrabold ${evening?.status === "finished" ? "bg-soft" : "bg-soft text-muted"}`}>
        🌙 {t("cabinet.evening")}: {eveningText}
      </p>
      <p className="text-sm font-bold text-muted">
        🕒 {t("cabinet.last_active", { date: lastActive(child.last_active_on, t) })}
      </p>
      <a href={`/family/${child.id}`} className="btn btn-soft !min-h-[2.75rem] text-base">
        📊 {t("report.open")}
      </a>
    </section>
  );
}

function Cabinet() {
  const t = useT();
  const { me } = useAuth();
  const [data, setData] = useState<ParentCabinet | null>(null);
  const [bot, setBot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<ParentCabinet>("/cabinet").then(setData).catch((e) => setError(errorCode(e)));
    api<PublicConfig>("/config")
      .then((c) => setBot(c.bot_username || null))
      .catch(() => setBot(null));
  }, []);

  if (!data && !error) return <Splash />;

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3 anim-rise">
        <Mascot size={56} />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-black leading-tight">👨‍👩‍👧 {t("cabinet.parent_title")}</h1>
          <p className="truncate text-sm font-bold text-muted">{me?.name}</p>
        </div>
        <IconButton href="/support" label={t("support.title")}>💬</IconButton>
        <IconButton href="/profile" label={t("profile.title")}>⚙️</IconButton>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {data && data.children.length === 0 && (
        <section className="card flex flex-col items-center gap-3 text-center">
          <Mascot size={80} />
          <h2 className="text-xl font-black">{t("cabinet.no_children_title")}</h2>
          <p className="font-semibold text-muted">{t("cabinet.no_children_text")}</p>
        </section>
      )}

      {data?.children.map((child) => <ChildCard key={child.id} child={child} />)}

      <nav className="flex flex-col gap-2" aria-label={t("cabinet.parent_title")}>
        <a href="/journal" className="option">
          <span className="text-3xl" aria-hidden="true">📒</span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span>{t("journal.title")}</span>
            <span className="text-sm font-bold text-muted">{t("journal.subtitle")}</span>
          </span>
          <span className="text-2xl text-muted" aria-hidden="true">›</span>
        </a>
        <a href="/family" className="option">
          <span className="text-3xl" aria-hidden="true">👨‍👩‍👧</span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span>{t("family.title")}</span>
            <span className="text-sm font-bold text-muted">{t("cabinet.family_hint")}</span>
          </span>
          <span className="text-2xl text-muted" aria-hidden="true">›</span>
        </a>
        {bot && (
          <a href={`https://t.me/${bot}`} target="_blank" rel="noopener noreferrer" className="option">
            <span className="text-3xl" aria-hidden="true">➕</span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span>{t("cabinet.add_child")}</span>
              <span className="text-sm font-bold text-muted">{t("cabinet.add_child_hint")}</span>
            </span>
            <span className="text-2xl text-muted" aria-hidden="true">›</span>
          </a>
        )}
      </nav>
    </Page>
  );
}

export default function ParentCabinetPage() {
  const router = useRouter();
  const { status, me } = useAuth();

  useEffect(() => {
    if (status === "guest") router.replace("/login?next=/parent");
    else if (status === "authed" && me?.role === "teacher") router.replace("/teacher");
    else if (status === "authed" && me?.role !== "parent") router.replace("/");
  }, [status, me, router]);

  if (status !== "authed" || me?.role !== "parent") return <Splash />;
  return <Cabinet />;
}
