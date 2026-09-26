"use client";

/* Дуэль: приглашение (код и ссылка), игра — по одному вопросу, 30 секунд на ответ
   (время считает сервер), ожидание соперника и итог с разбором. */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { MathText } from "@/components/MathText";
import { RequireStudent } from "@/components/RequireStudent";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { celebrate } from "@/lib/confetti";
import { useT } from "@/lib/i18n";
import type { DuelQuestion, DuelView } from "@/lib/types";

const LETTERS = ["A", "B", "C", "D"];

function Invite({ duel }: { duel: DuelView }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  if (!duel.code || duel.opponent) return null;
  const link = `${window.location.origin}/duels/join/${duel.code}`;
  const share = async () => {
    const text = t("duels.share_text", { topic: duel.topic, code: duel.code! });
    try {
      if (navigator.share) await navigator.share({ title: t("duels.title"), text, url: link });
      else {
        await navigator.clipboard.writeText(`${text} ${link}`);
        setCopied(true);
      }
    } catch {
      /* отменил «Поделиться» — ничего страшного */
    }
  };
  return (
    <section className="card flex flex-col items-center gap-2 text-center">
      <span className="text-sm font-extrabold text-muted">{t("duels.code")}</span>
      <span className="text-4xl font-black tracking-[0.3em]">{duel.code}</span>
      <button type="button" className="btn btn-soft" onClick={share}>📤 {copied ? t("duels.copied") : t("duels.share")}</button>
      {duel.public && <p className="text-xs font-bold text-muted">🌍 {t("duels.public_hint")}</p>}
    </section>
  );
}

function Play({ duel, onDone }: { duel: DuelView; onDone: () => void }) {
  const t = useT();
  const [q, setQ] = useState<DuelQuestion | null>(null);
  const [left, setLeft] = useState(30);
  const [picked, setPicked] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setPicked(null);
    setFeedback(null);
    try {
      const r = await api<{ question: DuelQuestion | null }>(`/duels/${duel.id}/next`, { method: "POST" });
      if (!r.question) onDone();
      else {
        setQ(r.question);
        setLeft(r.question.seconds_left);
      }
    } catch (e) {
      setError(errorCode(e));
    }
  }, [duel.id, onDone]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!q || feedback !== null) return;
    const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [q, feedback]);

  const answer = async (option: number) => {
    if (!q || picked !== null) return;
    setPicked(option);
    try {
      const r = await api<{ ok: boolean; done: boolean }>(`/duels/${duel.id}/answer`, { method: "POST", json: { n: q.n, option } });
      setFeedback(r.ok);
      setTimeout(() => (r.done ? onDone() : void load()), 900);
    } catch (e) {
      setError(errorCode(e));
    }
  };

  if (error) return <Notice tone="error">{t(`errors.${error}`)}</Notice>;
  if (!q) return <Splash />;
  return (
    <section className="flex flex-col gap-3" key={q.n}>
      <div className="flex items-center justify-between text-sm font-extrabold">
        <span>{t("duels.question", { n: q.n + 1, total: duel.total })}</span>
        <span className={left <= 5 ? "text-bad" : ""}>⏱ {left}s</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full rounded-full bg-primary transition-all duration-1000 ease-linear" style={{ width: `${(left / 30) * 100}%` }} />
      </div>
      <p className="card text-xl font-black"><MathText text={q.question} /></p>
      {q.options.map((o, i) => (
        <button
          key={i}
          type="button"
          className="option"
          disabled={picked !== null}
          data-state={picked === i && feedback !== null ? (feedback ? "correct" : "wrong") : undefined}
          onClick={() => answer(i)}
        >
          <span className="option-letter">{LETTERS[i]}</span>
          <span className="min-w-0 flex-1"><MathText text={o} /></span>
        </button>
      ))}
      {left === 0 && picked === null && <Notice>{t("duels.too_late")}</Notice>}
    </section>
  );
}

function Result({ duel }: { duel: DuelView }) {
  const t = useT();
  useEffect(() => {
    if (duel.winner === "me") celebrate(true);
  }, [duel.winner]);
  const secs = (ms: number) => (ms / 1000).toFixed(1);
  return (
    <>
      <section className="card flex flex-col items-center gap-2 text-center anim-pop">
        <span className="text-6xl" aria-hidden="true">{duel.winner === "me" ? "🏆" : duel.winner === "draw" ? "🤝" : "⚔️"}</span>
        <h2 className="text-2xl font-black">{duel.winner === "me" ? t("duels.won") : duel.winner === "draw" ? t("duels.draw") : t("duels.lost")}</h2>
        <div className="grid w-full grid-cols-2 gap-2">
          <div className="rounded-2xl bg-soft p-3">
            <div className="text-sm font-extrabold text-muted">{t("duels.you")}</div>
            <div className="text-3xl font-black">{duel.me.correct}/{duel.total}</div>
            <div className="text-xs font-bold text-muted">{secs(duel.me.ms)} s</div>
          </div>
          <div className="rounded-2xl bg-soft p-3">
            <div className="text-sm font-extrabold text-muted">{duel.opponent}</div>
            <div className="text-3xl font-black">{duel.them?.correct ?? 0}/{duel.total}</div>
            <div className="text-xs font-bold text-muted">{secs(duel.them?.ms ?? 0)} s</div>
          </div>
        </div>
        <p className="font-black text-primary">+{duel.reward} 🪙</p>
      </section>
      <ol className="flex flex-col gap-3">
        {duel.review?.map((r, i) => (
          <li key={i} className="card flex flex-col gap-2">
            <p className="font-black"><MathText text={r.question} /></p>
            {r.options.map((o, j) => (
              <div key={j} className="option !min-h-[2.5rem] !text-base" data-state={j === r.correct ? "correct" : j === r.mine ? "wrong" : undefined}>
                <span className="option-letter">{LETTERS[j]}</span>
                <span className="min-w-0 flex-1"><MathText text={o} /></span>
              </div>
            ))}
            {r.explanation && <p className="text-sm font-bold text-muted">💡 <MathText text={r.explanation} /></p>}
          </li>
        ))}
      </ol>
    </>
  );
}

function DuelScreen({ id }: { id: number }) {
  const t = useT();
  const [duel, setDuel] = useState<DuelView | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<DuelView>(`/duels/${id}`).then(setDuel).catch((e) => setError(errorCode(e)));
  }, [id]);

  useEffect(refresh, [refresh]);

  // Ждём соперника — обновляем раз в 10 секунд
  useEffect(() => {
    if (!duel || duel.status === "finished" || !duel.me.done) return;
    const tick = setInterval(refresh, 10_000);
    return () => clearInterval(tick);
  }, [duel, refresh]);

  if (!duel) {
    return error ? (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/duels" className="btn btn-soft">‹ {t("duels.title")}</Link>
      </Page>
    ) : (
      <Splash />
    );
  }

  return (
    <Page className="gap-4">
      <header className="flex items-center gap-3">
        <IconButton href="/duels" label={t("profile.back")}>‹</IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-black leading-tight">⚔️ {duel.topic}</h1>
          <p className="truncate text-sm font-bold text-muted">{duel.opponent ? `vs ${duel.opponent}` : t("duels.no_opponent")}</p>
        </div>
      </header>

      {duel.status === "finished" ? (
        <Result duel={duel} />
      ) : duel.status === "expired" ? (
        <Notice>{t("duels.expired_text")}</Notice>
      ) : playing ? (
        <Play duel={duel} onDone={() => { setPlaying(false); refresh(); }} />
      ) : duel.me.done ? (
        <>
          <section className="card flex flex-col items-center gap-2 text-center">
            <span className="text-5xl" aria-hidden="true">⏳</span>
            <p className="text-xl font-black">{t("duels.your_score", { n: duel.me.correct, total: duel.total })}</p>
            <p className="font-bold text-muted">{t("duels.waiting_text")}</p>
            <Dots />
          </section>
          <Invite duel={duel} />
        </>
      ) : (
        <>
          <Invite duel={duel} />
          <section className="card flex flex-col items-center gap-3 text-center">
            <p className="font-bold">{t("duels.rules", { total: duel.total })}</p>
            <button type="button" className="btn btn-primary btn-xl" onClick={() => setPlaying(true)}>
              ⚔️ {duel.me.answered > 0 ? t("duels.continue") : t("duels.play")}
            </button>
          </section>
        </>
      )}
    </Page>
  );
}

function Loader() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) return <Splash />;
  return <DuelScreen id={id} />;
}

export default function DuelPage() {
  return (
    <RequireStudent>
      <Loader />
    </RequireStudent>
  );
}
