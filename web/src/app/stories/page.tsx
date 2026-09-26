"use client";

/* Stories ученика: новые по своей теме (ИИ делает 6–10 карточек с мини-вопросами)
   и список всех — от учителя и своих. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { GameBanner, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { GRADES, SUBJECT_ICON } from "@/lib/subjects";
import type { Story, StoryFeed } from "@/lib/types";

function StoriesView() {
  const t = useT();
  const router = useRouter();
  const { me } = useAuth();
  const [feed, setFeed] = useState<StoryFeed | null>(null);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("math");
  const [grade, setGrade] = useState<number>(Math.max(5, me?.student?.grade ?? 5));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    setShowForm(new URLSearchParams(window.location.search).has("new"));
    api<StoryFeed>("/stories")
      .then((f) => {
        setFeed(f);
        if (f.stories.length === 0) setShowForm(true);
      })
      .catch((e) => setError(errorCode(e)));
  }, []);

  if (!feed && !error) return <Splash />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const story = await api<Story>("/stories", { method: "POST", json: { title: title.trim(), subject, grade } });
      router.push(`/stories/${story.id}`);
    } catch (err) {
      setError(errorCode(err));
      setBusy(false);
    }
  };

  return (
    <Page className="gap-5">
      {busy && <Thinking title={t("stories.thinking")} />}
      <GameBanner
        icon="📱"
        title={t("stories.title")}
        aside={feed && <span className="chip shrink-0 !min-h-[2.5rem]">🪙 {feed.coins}</span>}
      />

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {showForm ? (
        <form onSubmit={onSubmit} className="card flex flex-col gap-4 anim-rise">
          <h2 className="text-xl font-black">✨ {t("stories.new_title")}</h2>
          {feed && (
            <p className="text-sm font-bold text-muted">
              {t("stories.reward_hint", { story: feed.reward.story, answer: feed.reward.answer })}
            </p>
          )}
          <input
            className="field text-lg font-bold"
            value={title}
            onChange={(e) => setTitle(e.target.value.slice(0, 500))}
            placeholder={t("stories.placeholder")}
            aria-label={t("stories.new_title")}
            autoFocus
          />
          <fieldset>
            <legend className="label">{t("learn.subject")}</legend>
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(SUBJECT_ICON).map(([key, icon]) => (
                <button
                  key={key}
                  type="button"
                  className="chip min-h-[4rem] min-w-0 flex-col justify-center gap-0.5 rounded-2xl px-1 py-2 text-xs leading-tight"
                  aria-pressed={subject === key}
                  onClick={() => setSubject(key)}
                >
                  <span className="text-2xl leading-none" aria-hidden="true">{icon}</span>
                  <span className="max-w-full truncate">{t(`subjects.${key}`)}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="label">{t("learn.grade")}</legend>
            <div className="grid grid-cols-7 gap-1.5">
              {GRADES.map((g) => (
                <button key={g} type="button" className="chip justify-center px-0 text-lg" aria-pressed={grade === g} onClick={() => setGrade(g)}>
                  {g}
                </button>
              ))}
            </div>
          </fieldset>
          <button className="btn btn-primary" disabled={!title.trim() || busy}>
            📱 {t("stories.create")}
          </button>
        </form>
      ) : (
        <button type="button" className="btn btn-primary anim-rise" onClick={() => setShowForm(true)}>
          ✨ {t("stories.new_title")}
        </button>
      )}

      {feed && feed.stories.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="label">{t("stories.list")}</h2>
          {feed.stories.map((s) => (
            <Link key={s.id} href={`/stories/${s.id}`} className="option">
              <span
                className={`grid h-12 w-12 shrink-0 place-items-center rounded-full p-[3px] ${
                  s.status === "new" ? "bg-gradient-to-tr from-accent via-primary to-good" : "bg-line"
                }`}
                aria-hidden="true"
              >
                <span className="grid h-full w-full place-items-center rounded-full bg-soft text-2xl">{s.emoji}</span>
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate">{s.title}</span>
                <span className="text-sm font-bold text-muted">
                  {s.from_teacher ? `👩‍🏫 ${s.from_teacher} · ` : ""}
                  {t("stories.cards", { n: s.slides })}
                  {s.status === "done" ? ` · ✅ +${s.coins} 🪙` : ` · ${t("stories.unseen")}`}
                </span>
              </span>
              <span className="text-2xl text-muted" aria-hidden="true">›</span>
            </Link>
          ))}
        </section>
      )}
    </Page>
  );
}

export default function StoriesPage() {
  return (
    <RequireStudent>
      <StoriesView />
    </RequireStudent>
  );
}
