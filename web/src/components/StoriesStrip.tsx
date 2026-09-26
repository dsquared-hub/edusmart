"use client";

/* Лента Stories на главной ученика, как в Instagram: кружок «+» — новые Stories по теме,
   дальше — Stories от учителя и свои. Непросмотренные — с яркой обводкой. */
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { StoryBrief, StoryFeed } from "@/lib/types";

function Bubble({ story }: { story: StoryBrief }) {
  const fresh = story.status === "new";
  return (
    <Link href={`/stories/${story.id}`} className="flex w-[4.75rem] shrink-0 flex-col items-center gap-1.5" aria-label={story.title}>
      <span
        className={`grid h-[4.25rem] w-[4.25rem] place-items-center rounded-full p-[3px] ${
          fresh ? "bg-gradient-to-tr from-accent via-primary to-good" : "bg-line"
        }`}
      >
        <span className="grid h-full w-full place-items-center rounded-full border-[3px] border-bg bg-soft text-3xl" aria-hidden="true">
          {story.emoji}
        </span>
      </span>
      <span className={`w-full truncate text-center text-xs font-extrabold ${fresh ? "" : "text-muted"}`}>
        {story.from_teacher ? "👩‍🏫 " : ""}
        {story.title}
      </span>
    </Link>
  );
}

export function StoriesStrip() {
  const t = useT();
  const [stories, setStories] = useState<StoryBrief[] | null>(null);

  useEffect(() => {
    api<StoryFeed>("/stories")
      .then((feed) => setStories(feed.stories))
      .catch(() => setStories([]));
  }, []);

  if (stories === null) return null;

  return (
    <section aria-label={t("stories.title")} className="anim-rise">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="label !mb-0">📱 {t("stories.title")}</h2>
        {stories.length > 0 && (
          <Link href="/stories" className="text-sm font-extrabold text-primary">
            {t("stories.all")}
          </Link>
        )}
      </div>
      <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 pb-1">
        <Link href="/stories?new=1" className="flex w-[4.75rem] shrink-0 flex-col items-center gap-1.5">
          <span className="grid h-[4.25rem] w-[4.25rem] place-items-center rounded-full border-[3px] border-dashed border-primary/60 bg-surface text-3xl font-black text-primary">
            +
          </span>
          <span className="w-full truncate text-center text-xs font-extrabold text-primary">{t("stories.new_short")}</span>
        </Link>
        {stories.slice(0, 12).map((s) => (
          <Bubble key={s.id} story={s} />
        ))}
      </div>
    </section>
  );
}
