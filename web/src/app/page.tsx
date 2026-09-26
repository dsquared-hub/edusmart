"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Mascot } from "@/components/Mascot";
import { RequireStudent } from "@/components/RequireStudent";
import { StoriesStrip } from "@/components/StoriesStrip";
import { StudentGoals } from "@/components/StudentGoals";
import { Notice, Page, Splash } from "@/components/ui";
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
    <div className="flex min-w-0 flex-col items-center rounded-2xl bg-on-primary/10 px-1 py-2.5 text-center">
      <span className="text-xl" aria-hidden="true">{icon}</span>
      <span className="text-xl font-black leading-tight">{value}</span>
      <span className="w-full truncate text-[0.68rem] font-extrabold uppercase tracking-wide opacity-75">{label}</span>
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
      className={`option ${active ? "" : "pointer-events-none opacity-60"}`}
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
    <Page wide className="gap-5">
      <header className="flex items-center gap-3">
        <span className="logo-mark h-10 w-10 shrink-0 lg:hidden" aria-hidden="true" />
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight lg:text-3xl">
          <span className="hl-neon">{t("home.hello", { name: me.name.split(" ")[0] })}</span>
        </h1>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      {!consentOk && <Notice>{t("home.consent_wait")}</Notice>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-start">
        <div className="stagger flex min-w-0 flex-col gap-5">
          {progress && (
            /* Карточка героя: уровень и очки + свой носорог (ведёт в «Мой носорог») */
            <section
              className="hero-card relative overflow-hidden rounded-4xl p-5 text-on-primary"
              aria-label={t("home.level", { level: progress.level })}
            >
              <div className="flex items-center gap-3">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="whitespace-nowrap text-3xl font-black">⚡ {t("home.level", { level: progress.level })}</span>
                  <span className="text-sm font-bold opacity-80">
                    {t("home.to_next", { points: progress.points_to_next_level, next: progress.level + 1 })}
                  </span>
                  <div className="mt-2 h-3.5 overflow-hidden rounded-full bg-on-primary/20" aria-hidden="true">
                    <div
                      className="neon-bar h-full rounded-full transition-all duration-700"
                      style={{ width: `${Math.max(4, progress.level_progress * 100)}%` }}
                    />
                  </div>
                </div>
                <Link
                  href="/avatar"
                  aria-label={t("avatar.home_card")}
                  className="hero-avatar -my-3 shrink-0 transition-transform active:scale-95"
                >
                  <Mascot size={118} />
                </Link>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2">
                <Stat icon="⭐" value={progress.points} label={t("home.points")} />
                <Stat icon="🔥" value={t("home.streak_value", { n: progress.streak })} label={t("home.streak")} />
                <Stat icon="📚" value={progress.topics_completed} label={t("home.topics")} />
              </div>
            </section>
          )}

          <Link
            href="/learn"
            aria-disabled={!consentOk || noneLeft}
            className={`btn btn-primary btn-xl flex-col gap-0 py-4 ${!consentOk || noneLeft ? "pointer-events-none opacity-50" : ""}`}
          >
            <span>🤔 {t("home.cta")}</span>
            <span className="text-sm font-bold opacity-80">{t("home.cta_hint")}</span>
          </Link>

          {progress && progress.in_progress.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="label">▶️ {t("home.continue")}</h2>
              {progress.in_progress.map((topic) => (
                <TopicRow key={topic.id} topic={topic} />
              ))}
            </section>
          )}

          {consentOk && <StoriesStrip />}

          {progress && progress.recent.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="label">🏆 {t("home.recent")}</h2>
              {progress.recent.slice(0, 5).map((topic) => (
                <TopicRow key={topic.id} topic={topic} done />
              ))}
            </section>
          )}
        </div>

        <div className="stagger flex min-w-0 flex-col gap-5">
          {consentOk && (
            <section aria-labelledby="home-tools" className="flex flex-col gap-2">
              <h2 id="home-tools" className="label">🧰 {t("home.tools")}</h2>
              {/* Тренажёры — плитками, чтобы главная не превращалась в длинный список */}
              <div className="stagger grid grid-cols-2 gap-3">
                {TOOLS.filter((tool) => (me.student?.grade ?? 11) >= tool.minGrade).map((tool) => (
                  <Link key={tool.href} href={tool.href} className="tool-tile card flex flex-col gap-2 !p-4">
                    <span className="tool-icon grid h-12 w-12 place-items-center rounded-2xl text-2xl" aria-hidden="true">
                      {tool.icon}
                    </span>
                    <span className="font-black leading-tight">{t(`${tool.key}.home_card`)}</span>
                    <span className="text-xs font-bold leading-snug text-muted">{t(`${tool.key}.home_hint`)}</span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {consentOk && <EveningCard />}

          {consentOk && <StudentGoals />}

          {progress && (
            <p className="text-center text-sm font-bold text-muted">
              {t("home.left_today", { left: progress.explanations_left_today, limit: progress.daily_limit })}
            </p>
          )}
        </div>
      </div>
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
