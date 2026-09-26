"use client";

/* Квесты Paper-to-Digital: список. /quests?topic=ID (с экрана «Тема пройдена») сразу
   создаёт квест по этой теме и открывает его. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { GameBanner, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { PaperQuest } from "@/lib/types";

type QuestList = { quests: PaperQuest[]; reward: number; per_day: number };

function Quests() {
  const t = useT();
  const router = useRouter();
  const [data, setData] = useState<QuestList | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const topic = new URLSearchParams(window.location.search).get("topic");
    if (topic && /^\d+$/.test(topic)) {
      setCreating(true);
      api<PaperQuest>("/quests", { method: "POST", json: { topic_id: Number(topic) } })
        .then((q) => router.replace(`/quests/${q.id}`))
        .catch((e) => {
          setError(errorCode(e));
          setCreating(false);
        });
    }
    api<QuestList>("/quests").then(setData).catch((e) => setError(errorCode(e)));
  }, [router]);

  if (creating) return <Thinking title={t("quests.creating")} />;
  if (!data && !error) return <Splash />;

  return (
    <Page className="gap-5">
      <GameBanner icon="📄" title={t("quests.title")}>
        <p className="text-base">{t("quests.intro", { coins: data?.reward ?? 6 })}</p>
        <p className="mt-1 opacity-80">{t("quests.how")}</p>
      </GameBanner>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {data && data.quests.length === 0 && <Notice>{t("quests.empty")}</Notice>}

      {data && data.quests.length > 0 && (
        <section className="flex flex-col gap-2">
          {data.quests.map((q) => (
            <Link key={q.id} href={`/quests/${q.id}`} className="option">
              <span className="text-3xl" aria-hidden="true">{q.status === "passed" ? "✅" : "📄"}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="line-clamp-2 [overflow-wrap:anywhere]">{q.task}</span>
                <span className="text-sm font-bold text-muted">
                  {q.status === "passed" ? `+${q.coins} 🪙` : t("quests.attempts", { n: q.attempts_left })}
                </span>
              </span>
              <span className="text-2xl text-muted" aria-hidden="true">›</span>
            </Link>
          ))}
        </section>
      )}

      <Link href="/learn" className="btn btn-soft">🤔 {t("quests.learn_more")}</Link>
    </Page>
  );
}

export default function QuestsPage() {
  return (
    <RequireStudent>
      <Quests />
    </RequireStudent>
  );
}
