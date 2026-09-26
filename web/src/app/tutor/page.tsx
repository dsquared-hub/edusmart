"use client";

/* Сократовский тьютор: новая задача (текст или фото) и прошлые диалоги.
   Носорог не решает за ученика — ведёт наводящими вопросами. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Mascot } from "@/components/Mascot";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { shrinkImage } from "@/lib/image";
import { subjectIcon } from "@/lib/subjects";
import type { TutorBrief, TutorDialog } from "@/lib/types";

function TutorHome() {
  const t = useT();
  const router = useRouter();
  const { me } = useAuth();
  const fileInput = useRef<HTMLInputElement>(null);
  const [dialogs, setDialogs] = useState<TutorBrief[] | null>(null);
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ dialogs: TutorBrief[] }>("/tutor")
      .then((r) => setDialogs(r.dialogs))
      .catch((e) => setError(errorCode(e)));
  }, []);

  if (!dialogs && !error) return <Splash />;

  const canSubmit = (text.trim().length > 0 || photo !== null) && !busy;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("text", text.trim());
      if (me?.student?.grade) form.set("grade", String(me.student.grade));
      if (photo) form.set("photo", await shrinkImage(photo), "task.jpg");
      const dialog = await api<TutorDialog>("/tutor", { method: "POST", form });
      router.push(`/tutor/${dialog.id}`);
    } catch (err) {
      setError(errorCode(err));
      setBusy(false);
    }
  };

  return (
    <Page className="gap-5">
      {busy && <Thinking title={t("tutor.thinking")} />}
      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">🦏 {t("tutor.title")}</h1>
      </header>

      <section className="card flex items-center gap-4 anim-rise">
        <Mascot size={72} />
        <p className="font-bold">{t("tutor.intro")}</p>
      </section>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <form onSubmit={onSubmit} className="card flex flex-col gap-3 anim-rise">
        <textarea
          className="field min-h-[6.5rem] resize-none text-lg font-bold"
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, 500))}
          placeholder={t("tutor.placeholder")}
          aria-label={t("tutor.placeholder")}
          rows={3}
        />
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/*"
          className="sr-only"
          tabIndex={-1}
          onChange={(e) => {
            setPhoto(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />
        <div className="flex gap-2">
          <button type="button" className="btn btn-soft flex-1 !min-h-[3rem] text-base" onClick={() => fileInput.current?.click()}>
            📷 {photo ? t("learn.photo_change") : t("learn.photo_add")}
          </button>
          {photo && (
            <button type="button" className="btn btn-soft !w-auto !min-h-[3rem] px-4" onClick={() => setPhoto(null)} aria-label={t("learn.photo_remove")}>
              ✕
            </button>
          )}
        </div>
        {photo && <p className="text-sm font-bold text-muted">📎 {photo.name}</p>}
        <button className="btn btn-primary" disabled={!canSubmit}>
          🦏 {t("tutor.start")}
        </button>
      </form>

      {dialogs && dialogs.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="label">{t("tutor.history")}</h2>
          {dialogs.map((d) => (
            <Link key={d.id} href={`/tutor/${d.id}`} className="option">
              <span className="text-3xl" aria-hidden="true">{d.status === "solved" ? "✅" : subjectIcon(d.subject)}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate">{d.title}</span>
                <span className="text-sm font-bold text-muted">
                  {d.status === "solved" ? t("tutor.solved_short", { points: d.points }) : t("tutor.in_progress")}
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

export default function TutorPage() {
  return (
    <RequireStudent>
      <TutorHome />
    </RequireStudent>
  );
}
