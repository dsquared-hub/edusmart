"use client";

/* Просмотр Stories, как в Instagram: полоски прогресса сверху, тап справа — дальше,
   слева — назад. На карточке с вопросом дальше можно только после ответа: засчитывается
   первая попытка. В конце — EduCoin (один раз). */
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Dots, Notice, Page, Splash } from "@/components/ui";
import { MathText } from "@/components/MathText";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Story, StoryAnswer, StoryCard, StoryDone } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D", "E"];

function Question({
  card,
  onAnswer,
  busy,
}: {
  card: StoryCard;
  onAnswer: (option: number) => void;
  busy: boolean;
}) {
  const t = useT();
  const [picked, setPicked] = useState<number | null>(null);
  const answered = card.answered && card.correct !== undefined;
  return (
    <div className="flex flex-col gap-2" onClick={(e) => e.stopPropagation()}>
      <p className="text-lg font-black">🤔 <MathText text={card.question ?? ""} /></p>
      {card.options?.map((option, i) => {
        const state = !answered ? undefined : i === card.correct ? "correct" : i === picked ? "wrong" : undefined;
        return (
          <button
            key={i}
            type="button"
            className="option !min-h-[3.25rem] !text-base"
            data-state={state}
            disabled={answered || busy}
            onClick={() => {
              setPicked(i);
              onAnswer(i);
            }}
          >
            <span className="option-letter">{LETTERS[i]}</span>
            <span className="min-w-0 flex-1"><MathText text={option} /></span>
          </button>
        );
      })}
      {answered && (
        <Notice>
          {picked !== null && picked === card.correct ? "✅ " : "💡 "}
          {card.explanation || t("stories.right_is", { option: card.options?.[card.correct!] ?? "" })}
        </Notice>
      )}
    </div>
  );
}

function Finish({ result, story }: { result: StoryDone; story: Story }) {
  const t = useT();
  return (
    <Page className="justify-center gap-5 text-center">
      <div className="text-7xl anim-pop" aria-hidden="true">{result.awarded ? "🎉" : "✅"}</div>
      <h1 className="text-3xl font-black">{t("stories.done_title")}</h1>
      <p className="text-lg font-bold text-muted">{story.title}</p>
      <section className="card flex flex-col gap-2 anim-rise">
        {result.awarded ? (
          <p className="text-3xl font-black text-primary">+{result.coins} 🪙 EduCoin</p>
        ) : (
          <p className="font-bold text-muted">{t("stories.already_awarded", { coins: result.coins })}</p>
        )}
        {result.questions > 0 && (
          <p className="font-bold">{t("stories.first_try", { n: result.first_try, total: result.questions })}</p>
        )}
        <p className="text-sm font-bold text-muted">{t("stories.balance", { coins: result.total_coins })}</p>
      </section>
      <div className="flex flex-col gap-2">
        <Link href="/stories?new=1" className="btn btn-primary">✨ {t("stories.more")}</Link>
        <Link href="/avatar" className="btn btn-soft">🦏 {t("avatar.home_card")}</Link>
        <Link href="/" className="btn btn-soft">{t("stories.home")}</Link>
      </div>
    </Page>
  );
}

function Viewer({ id }: { id: number }) {
  const t = useT();
  const router = useRouter();
  const [story, setStory] = useState<Story | null>(null);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StoryDone | null>(null);

  useEffect(() => {
    api<Story>(`/stories/${id}`).then(setStory).catch((e) => setError(errorCode(e)));
  }, [id]);

  const card = story?.cards[index];
  const blocked = !!card?.question && !card.answered;
  const last = story ? index === story.cards.length - 1 : false;

  const finish = useCallback(async () => {
    setBusy(true);
    try {
      setResult(await api<StoryDone>(`/stories/${id}/complete`, { method: "POST" }));
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  }, [id]);

  const next = useCallback(() => {
    if (!story || blocked || busy) return;
    if (last) void finish();
    else setIndex((i) => i + 1);
  }, [story, blocked, busy, last, finish]);

  const prev = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "Escape") router.push("/stories");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, router]);

  const answer = async (option: number) => {
    if (!story || busy) return;
    setBusy(true);
    try {
      const r = await api<StoryAnswer>(`/stories/${id}/answer`, { method: "POST", json: { slide: index, option } });
      setStory({
        ...story,
        cards: story.cards.map((c, i) => (i === index ? { ...c, answered: true, correct: r.correct, explanation: r.explanation } : c)),
      });
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  if (result && story) return <Finish result={result} story={story} />;
  if (!story) {
    return error ? (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/stories" className="btn btn-soft">‹ {t("stories.title")}</Link>
      </Page>
    ) : (
      <Splash />
    );
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-center bg-bg">
      <div
        className="relative flex h-full w-full max-w-md select-none flex-col bg-gradient-to-b from-primary/25 via-soft to-bg px-4 pb-6 pt-3"
        onClick={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          if (e.clientX - box.left < box.width * 0.3) prev();
          else next();
        }}
      >
        <div className="flex gap-1" aria-hidden="true">
          {story.cards.map((_, i) => (
            <span key={i} className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink/15">
              <span className={`block h-full rounded-full bg-primary transition-all duration-300 ${i <= index ? "w-full" : "w-0"}`} />
            </span>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-sm font-extrabold text-muted">
            {story.from_teacher ? `👩‍🏫 ${story.from_teacher} · ` : ""}
            {story.title}
          </span>
          <span className="text-sm font-extrabold text-muted" aria-live="polite">
            {index + 1}/{story.cards.length}
          </span>
          <button
            type="button"
            className="grid h-10 w-10 place-items-center rounded-full bg-surface text-xl font-black"
            aria-label={t("stories.close")}
            onClick={(e) => {
              e.stopPropagation();
              router.push("/stories");
            }}
          >
            ✕
          </button>
        </div>

        <article key={index} className="flex flex-1 flex-col justify-center gap-4 overflow-y-auto py-4 anim-rise">
          {card!.emoji && <div className="text-7xl leading-none" aria-hidden="true">{card!.emoji}</div>}
          <h1 className="text-3xl font-black leading-tight">{card!.title}</h1>
          <p className="text-2xl font-bold leading-snug"><MathText text={card!.text} /></p>
          {card!.question && <Question key={`q${index}`} card={card!} onAnswer={answer} busy={busy} />}
        </article>

        {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
          <button type="button" className="btn btn-soft !w-auto px-5" onClick={prev} disabled={index === 0} aria-label={t("stories.prev")}>
            ‹
          </button>
          <button type="button" className="btn btn-primary flex-1" onClick={next} disabled={blocked || busy}>
            {busy ? <Dots /> : blocked ? t("stories.answer_first") : last ? `🏁 ${t("stories.finish")}` : `${t("stories.next")} ›`}
          </button>
        </div>
      </div>
    </div>
  );
}

function StoryPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) return <Splash />;
  return <Viewer id={id} />;
}

export default function StoryViewerPage() {
  return (
    <RequireStudent>
      <StoryPage />
    </RequireStudent>
  );
}
