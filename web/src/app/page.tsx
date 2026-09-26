"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Mascot } from "@/components/Mascot";
import { RequireStudent } from "@/components/RequireStudent";
import { StoriesStrip } from "@/components/StoriesStrip";
import { StudentGoals } from "@/components/StudentGoals";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { subjectIcon } from "@/lib/subjects";
import type { Progress, TopicBrief } from "@/lib/types";

/** Тренажёры на главной ученика (ДТМ — с 8 класса, IELTS — с 10-го, как в Dev-Spec). */
const TOOLS = [
  { key: "tutor", href: "/tutor", icon: "🦏", minGrade: 0 },
  { key: "quests", href: "/quests", icon: "📄", minGrade: 0 },
  { key: "duels", href: "/duels", icon: "⚔️", minGrade: 0 },
  { key: "dtm", href: "/dtm", icon: "🎓", minGrade: 8 },
  { key: "ielts", href: "/ielts", icon: "🇬🇧", minGrade: 10 },
] as const;

function Stat({ icon, value, label }: { icon: string; value: string | number; label: string }) {
  return (
    <div className="flex flex-1 flex-col items-center rounded-2xl bg-soft px-2 py-3">
      <span className="text-2xl" aria-hidden="true">{icon}</span>
      <span className="text-2xl font-black leading-tight">{value}</span>
      <span className="text-xs font-extrabold uppercase tracking-wide text-muted">{label}</span>
    </div>
  );
}

function TopicRow({ topic, done }: { topic: TopicBrief; done?: boolean }) {
  const t = useT();
  const icon = subjectIcon(topic.subject);
  return (
    <Link href={`/learn/${topic.id}`} className="option">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-soft text-2xl" aria-hidden="true">
        {done ? "✅" : icon}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate">{topic.title}</span>
        <span className="text-sm font-bold text-muted">
          {done
            ? `+${topic.points_earned} ⭐`
            : t("home.step_of", { n: topic.current_step + 1, total: topic.total_steps })}
          {topic.source === "bot" && ` · ✈️ ${t("home.from_bot")}`}
        </span>
      </span>
      <span className="text-2xl text-muted" aria-hidden="true">›</span>
    </Link>
  );
}

type EveningStatus = { open: boolean; window: [string, string]; test: { status: string; score: number; total: number } | null };

/** Кнопка «Вечерний тест»: активна с 17:00 до 22:00 по Ташкенту. */
function EveningCard() {
  const t = useT();
  const [status, setStatus] = useState<EveningStatus | null>(null);
  useEffect(() => {
    api<EveningStatus>("/v1/evening").then(setStatus).catch(() => setStatus(null));
  }, []);
  if (!status) return null;
  const done = status.test?.status === "finished";
  const active = status.open && !done;
  return (
    <Link
      href="/evening"
      aria-disabled={!active}
      className={`option anim-rise ${active ? "" : "pointer-events-none opacity-60"}`}
    >
      <span className="text-3xl" aria-hidden="true">🌙</span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span>{t("evening.title")}</span>
        <span className="text-sm font-bold text-muted">
          {done
            ? t("evening.already_done", { score: status.test!.score, total: status.test!.total })
            : status.open
              ? t("evening.card_hint")
              : t("evening.closed", { from: status.window[0], to: status.window[1] })}
        </span>
      </span>
      {active && <span className="text-2xl text-muted" aria-hidden="true">›</span>}
    </Link>
  );
}

function Home() {
  const t = useT();
  const { me } = useAuth();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Progress>("/progress").then(setProgress).catch((e) => setError(errorCode(e)));
  }, []);

  if (!me) return null;
  if (!progress && !error) return <Splash />;

  const consentOk = me.student?.consent_confirmed ?? true;
  const noneLeft = progress ? progress.explanations_left_today <= 0 : false;

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3 anim-rise">
        {/* После входа — свой аватар; нажатие ведёт в «Мой носорог» */}
        <Link href="/avatar" aria-label={t("avatar.home_card")} className="shrink-0 transition-transform active:scale-95">
          <Mascot size={76} />
        </Link>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">
          <span className="hl-neon">{t("home.hello", { name: me.name.split(" ")[0] })}</span>
        </h1>
        <IconButton href="/profile" label={t("profile.title")}>⚙️</IconButton>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {consentOk && <StoriesStrip />}

      {progress && (
        <section className="card flex flex-col gap-4 anim-rise" aria-label={t("home.level", { level: progress.level })}>
          <div className="flex flex-col gap-0.5">
            <span className="whitespace-nowrap text-2xl font-black">⚡ {t("home.level", { level: progress.level })}</span>
            <span className="text-sm font-bold text-muted">
              {t("home.to_next", { points: progress.points_to_next_level, next: progress.level + 1 })}
            </span>
          </div>
          <div className="h-4 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <div
              className="neon-bar h-full rounded-full transition-all duration-700"
              style={{ width: `${Math.max(4, progress.level_progress * 100)}%` }}
            />
          </div>
          <div className="flex gap-2">
            <Stat icon="⭐" value={progress.points} label={t("home.points")} />
            <Stat icon="🔥" value={t("home.streak_value", { n: progress.streak })} label={t("home.streak")} />
            <Stat icon="📚" value={progress.topics_completed} label={t("home.topics")} />
          </div>
        </section>
      )}

      {!consentOk && <Notice>{t("home.consent_wait")}</Notice>}

      <Link
        href="/learn"
        aria-disabled={!consentOk || noneLeft}
        className={`btn btn-primary btn-xl flex-col gap-0 py-4 anim-rise ${!consentOk || noneLeft ? "pointer-events-none opacity-50" : ""}`}
      >
        <span>🤔 {t("home.cta")}</span>
        <span className="text-sm font-bold opacity-80">{t("home.cta_hint")}</span>
      </Link>

      {consentOk && (
        <section aria-labelledby="home-tools" className="flex flex-col gap-2">
          <h2 id="home-tools" className="label">🧰 {t("home.tools")}</h2>
          {/* Тренажёры — плитками, чтобы главная не превращалась в длинный список */}
          <div className="grid grid-cols-2 gap-2">
            {TOOLS.filter((tool) => (me.student?.grade ?? 11) >= tool.minGrade).map((tool) => (
              <Link key={tool.href} href={tool.href} className="card flex flex-col gap-1 !p-4 anim-rise">
                <span className="text-3xl" aria-hidden="true">{tool.icon}</span>
                <span className="font-black leading-tight">{t(`${tool.key}.home_card`)}</span>
                <span className="text-xs font-bold leading-snug text-muted">{t(`${tool.key}.home_hint`)}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {consentOk && <EveningCard />}

      {consentOk && <StudentGoals />}

      <Link href="/avatar" className="option anim-rise">
        <span className="text-3xl" aria-hidden="true">🦏</span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span>{t("avatar.home_card")}</span>
          <span className="text-sm font-bold text-muted">{t("avatar.home_hint")}</span>
        </span>
        <span className="text-2xl text-muted" aria-hidden="true">›</span>
      </Link>

      {progress && progress.in_progress.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="label">▶️ {t("home.continue")}</h2>
          {progress.in_progress.map((topic) => (
            <TopicRow key={topic.id} topic={topic} />
          ))}
        </section>
      )}

      {progress && progress.recent.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="label">🏆 {t("home.recent")}</h2>
          {progress.recent.slice(0, 5).map((topic) => (
            <TopicRow key={topic.id} topic={topic} done />
          ))}
        </section>
      )}

      {progress && (
        <p className="mt-auto text-center text-sm font-bold text-muted">
          {t("home.left_today", { left: progress.explanations_left_today, limit: progress.daily_limit })}
        </p>
      )}
    </Page>
  );
}

export default function HomePage() {
  return (
    <RequireStudent>
      <Home />
    </RequireStudent>
  );
}
