"use client";

/* Квест: задача → реши в тетради → сфоткай (камера телефона или ноутбука) → проверка.
   Верно — EduCoin ×2 и оценка аккуратности; нет — пометки, где ошибка, и ещё попытка. */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { MathText } from "@/components/MathText";
import { api, errorCode } from "@/lib/api";
import { celebrate } from "@/lib/confetti";
import { useT } from "@/lib/i18n";
import { shrinkImage } from "@/lib/image";
import type { PaperQuest, QuestCheck } from "@/lib/types";

function Quest({ id }: { id: number }) {
  const t = useT();
  const camera = useRef<HTMLInputElement>(null);
  const [quest, setQuest] = useState<PaperQuest | null>(null);
  const [check, setCheck] = useState<QuestCheck | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<PaperQuest>(`/quests/${id}`).then(setQuest).catch((e) => setError(errorCode(e)));
  }, [id]);

  // Превью фото — только в памяти вкладки
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  if (!quest) {
    return error ? (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/quests" className="btn btn-soft">‹ {t("quests.title")}</Link>
      </Page>
    ) : (
      <Splash />
    );
  }

  const send = async (file: File) => {
    setBusy(true);
    setError(null);
    setPreview(URL.createObjectURL(file));
    try {
      const form = new FormData();
      form.set("photo", await shrinkImage(file), "page.jpg");
      const result = await api<QuestCheck>(`/quests/${id}/photo`, { method: "POST", form });
      setCheck(result);
      setQuest(result.quest);
      if (result.awarded) celebrate(true);
    } catch (e) {
      setError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  const passed = quest.status === "passed";

  return (
    <Page className="gap-5">
      {busy && <Thinking title={t("quests.checking")} />}
      <header className="flex items-center gap-3">
        <IconButton href="/quests" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">📄 {t("quests.quest")}</h1>
        <span className="chip shrink-0 !min-h-[2.5rem]">🪙 ×2</span>
      </header>

      <section className="card flex flex-col gap-2 anim-rise">
        <span className="label !mb-0">{t("quests.task")}</span>
        <p className="text-xl font-black [overflow-wrap:anywhere]"><MathText text={quest.task} /></p>
        {quest.answer && <p className="text-sm font-bold text-muted">🔑 {t("quests.answer", { answer: quest.answer })}</p>}
      </section>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {preview && (
        <div className="relative overflow-hidden rounded-3xl border-[length:var(--border-w)] border-line bg-surface">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt={t("quests.photo_alt")} className="w-full object-contain" />
          {/* Пометки ошибок — координаты доли от размеров фото */}
          {check?.marks.map((m, i) => (
            <span
              key={i}
              className="absolute rounded-md border-[3px] border-bad bg-bad/10"
              style={{ left: `${m.box[0] * 100}%`, top: `${m.box[1] * 100}%`, width: `${m.box[2] * 100}%`, height: `${m.box[3] * 100}%` }}
              title={m.note}
            />
          ))}
        </div>
      )}

      {check && (
        <section className={`card flex flex-col gap-2 anim-pop ${check.passed ? "bg-good/10" : ""}`} aria-live="polite">
          {check.passed ? (
            <p className="text-2xl font-black">
              🎉 {check.awarded ? t("quests.passed", { coins: quest.coins }) : t("quests.already")}
            </p>
          ) : check.blurry ? (
            <p className="text-lg font-black">📷 {t("quests.blurry")}</p>
          ) : (
            <p className="text-lg font-black">🤔 {t("quests.not_yet", { score: quest.score ?? 0, max: quest.max_score })}</p>
          )}
          {quest.comment && <p className="font-bold">💬 {quest.comment}</p>}
          {check.marks.map((m, i) => (
            <p key={i} className="text-sm font-bold text-bad">✏️ {m.note}</p>
          ))}
          {quest.neatness !== null && <p className="text-sm font-bold text-muted">✍️ {t("quests.neatness", { n: quest.neatness })}</p>}
          {check.passed && <p className="text-sm font-bold text-muted">{t("stories.balance", { coins: check.total_coins })}</p>}
        </section>
      )}

      {!passed && quest.attempts_left > 0 && (
        <>
          <input
            ref={camera}
            type="file"
            accept="image/*"
            capture="environment"
            className="sr-only"
            tabIndex={-1}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) void send(file);
            }}
          />
          <p className="text-center text-sm font-bold text-muted">{t("quests.how")}</p>
          <button type="button" className="btn btn-primary btn-xl" onClick={() => camera.current?.click()} disabled={busy}>
            📷 {check ? t("quests.retake") : t("quests.snap")}
          </button>
          <p className="text-center text-sm font-bold text-muted">
            {t("quests.attempts", { n: quest.attempts_left })} · 🔒 {t("learn.photo_note")}
          </p>
        </>
      )}

      {(passed || quest.attempts_left === 0) && (
        <div className="flex flex-col gap-2">
          <Link href="/quests" className="btn btn-primary">📄 {t("quests.title")}</Link>
          <Link href="/" className="btn btn-soft">{t("stories.home")}</Link>
        </div>
      )}
    </Page>
  );
}

function QuestPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) return <Splash />;
  return <Quest id={id} />;
}

export default function PaperQuestPage() {
  return (
    <RequireStudent>
      <QuestPage />
    </RequireStudent>
  );
}
