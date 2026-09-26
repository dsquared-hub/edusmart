"use client";

/* Диалог с сократовским тьютором: пузыри сообщений, ввод ответа. «Решено» — когда
   ученик сам назвал верный ответ (это подтверждает второй запрос на сервере). */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Mascot } from "@/components/Mascot";
import { RequireStudent } from "@/components/RequireStudent";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { MathText } from "@/components/MathText";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { TutorDialog } from "@/lib/types";

function Chat({ id }: { id: number }) {
  const t = useT();
  const [dialog, setDialog] = useState<TutorDialog | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<TutorDialog>(`/tutor/${id}`).then(setDialog).catch((e) => setError(errorCode(e)));
  }, [id]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [dialog?.messages.length, busy]);

  if (!dialog) {
    return error ? (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/tutor" className="btn btn-soft">‹ {t("tutor.title")}</Link>
      </Page>
    ) : (
      <Splash />
    );
  }

  const solved = dialog.status === "solved";
  const canSend = text.trim().length > 0 && !busy && !solved && dialog.turns_left > 0;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    const message = text.trim();
    setBusy(true);
    setError(null);
    // Сообщение ученика видно сразу, ответ носорога — когда придёт
    setDialog({ ...dialog, messages: [...dialog.messages, { role: "student", text: message, at: new Date().toISOString() }] });
    setText("");
    try {
      setDialog(await api<TutorDialog>(`/tutor/${id}/message`, { method: "POST", json: { text: message } }));
    } catch (err) {
      setError(errorCode(err));
      setDialog(dialog);
      setText(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="gap-4">
      <header className="flex items-center gap-3">
        <IconButton href="/tutor" label={t("profile.back")}>‹</IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-black leading-tight">🦏 {t("tutor.title")}</h1>
          <p className="truncate text-sm font-bold text-muted">{dialog.problem}</p>
        </div>
      </header>

      <ol className="flex flex-1 flex-col gap-3" aria-live="polite">
        {dialog.messages.map((m, i) =>
          m.role === "tutor" ? (
            <li key={i} className="flex items-end gap-2 anim-rise">
              <Mascot size={36} />
              <p className="max-w-[80%] whitespace-pre-wrap rounded-3xl rounded-bl-md bg-surface px-4 py-3 font-bold shadow-sm [overflow-wrap:anywhere]">
                <MathText text={m.text} />
              </p>
            </li>
          ) : (
            <li key={i} className="flex justify-end anim-rise">
              <p className="max-w-[80%] whitespace-pre-wrap rounded-3xl rounded-br-md bg-primary px-4 py-3 font-bold text-on-primary [overflow-wrap:anywhere]">
                <MathText text={m.text} />
              </p>
            </li>
          ),
        )}
        {busy && (
          <li className="flex items-end gap-2">
            <Mascot size={36} mood="thinking" />
            <span className="rounded-3xl bg-surface px-4 py-3"><Dots /></span>
          </li>
        )}
      </ol>
      <div ref={bottom} />

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      {solved ? (
        <section className="card flex flex-col items-center gap-2 text-center anim-pop">
          <div className="text-5xl" aria-hidden="true">🎉</div>
          <p className="text-xl font-black">{t("tutor.solved", { points: dialog.points })}</p>
          <div className="flex w-full gap-2">
            <Link href="/tutor" className="btn btn-primary flex-1">🦏 {t("tutor.new")}</Link>
            <Link href="/" className="btn btn-soft flex-1">{t("stories.home")}</Link>
          </div>
        </section>
      ) : dialog.turns_left === 0 ? (
        <Notice>{t("errors.tutor_turns_limit")}</Notice>
      ) : (
        <form onSubmit={onSubmit} className="safe-bottom sticky bottom-0 -mx-4 flex gap-2 bg-bg px-4 pb-2 pt-2">
          <input
            className="field min-w-0 flex-1"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, 1000))}
            placeholder={t("tutor.answer_placeholder")}
            aria-label={t("tutor.answer_placeholder")}
            autoFocus
          />
          <button className="btn btn-primary !w-auto px-5" disabled={!canSend} aria-label={t("tutor.send")}>
            {busy ? <Dots /> : "➤"}
          </button>
        </form>
      )}
    </Page>
  );
}

function DialogPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) return <Splash />;
  return <Chat id={id} />;
}

export default function TutorDialogPage() {
  return (
    <RequireStudent>
      <DialogPage />
    </RequireStudent>
  );
}
