"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, Page } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { shrinkImage } from "@/lib/image";
import { GRADES } from "@/lib/subjects";
import type { Topic } from "@/lib/types";

const SUBJECTS = [
  ["math", "🔢"],
  ["russian", "📝"],
  ["uzbek", "📖"],
  ["english", "🇬🇧"],
  ["physics", "⚡"],
  ["nature", "🌿"],
  ["history", "🏛️"],
  ["other", "✨"],
] as const;

function LearnForm() {
  const t = useT();
  const router = useRouter();
  const { me } = useAuth();
  const fileInput = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState<string>("math");
  const [grade, setGrade] = useState<number>(Math.max(5, me?.student?.grade ?? 5));
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assignment, setAssignment] = useState<string | null>(null);

  // Задание от родителя / учителя: тема уже известна (/learn?title=…&assignment=…)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const preset = params.get("title");
    if (preset) setTitle(preset.slice(0, 500));
    const id = params.get("assignment");
    if (id && /^\d+$/.test(id)) setAssignment(id);
  }, []);

  // Превью живёт только в памяти вкладки
  useEffect(() => {
    if (!photo) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  const canSubmit = (title.trim().length > 0 || photo !== null) && !busy;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("title", title.trim());
      form.set("subject", subject);
      form.set("grade", String(grade));
      if (photo) form.set("photo", await shrinkImage(photo), "task.jpg");
      if (assignment) form.set("assignment_id", assignment);
      const topic = await api<Topic>("/explain", { method: "POST", form });
      router.push(`/learn/${topic.id}`);
    } catch (err) {
      setError(errorCode(err));
      setBusy(false);
    }
  };

  return (
    <Page className="gap-5">
      {busy && <Thinking />}

      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="text-2xl font-black leading-tight">{t("learn.title")}</h1>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <form onSubmit={onSubmit} className="flex flex-1 flex-col gap-5">
        <textarea
          className="field min-h-[7.5rem] resize-none text-xl font-bold"
          value={title}
          onChange={(e) => setTitle(e.target.value.slice(0, 500))}
          placeholder={t("learn.placeholder")}
          aria-label={t("learn.title")}
          rows={3}
          autoFocus={!assignment}
        />

        <div className="flex flex-col gap-2">
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
          {preview ? (
            <div className="relative overflow-hidden rounded-3xl border-[length:var(--border-w)] border-line bg-surface anim-pop">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="" className="max-h-64 w-full object-contain" />
              <div className="flex gap-2 p-3">
                <button type="button" className="btn btn-soft min-h-[3rem] text-base" onClick={() => fileInput.current?.click()}>
                  📷 {t("learn.photo_change")}
                </button>
                <button type="button" className="btn btn-soft min-h-[3rem] text-base" onClick={() => setPhoto(null)}>
                  ✕ {t("learn.photo_remove")}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="flex min-h-[6rem] w-full flex-col items-center justify-center gap-1 rounded-3xl border-[3px] border-dashed border-primary/60 bg-surface text-lg font-extrabold text-primary"
            >
              <span className="text-4xl" aria-hidden="true">📷</span>
              {t("learn.photo_add")}
            </button>
          )}
          <p className="text-center text-sm font-semibold text-muted">🔒 {t("learn.photo_note")}</p>
        </div>

        <fieldset>
          <legend className="label">{t("learn.subject")}</legend>
          {/* 8 предметов — две ровные строки по 4 */}
          <div className="grid grid-cols-4 gap-2">
            {SUBJECTS.map(([key, icon]) => (
              <button
                key={key}
                type="button"
                className="chip min-h-[4.25rem] min-w-0 flex-col justify-center gap-0.5 rounded-2xl px-1 py-2 text-xs leading-tight sm:text-sm"
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
              <button
                key={g}
                type="button"
                className="chip justify-center px-0 text-lg"
                aria-pressed={grade === g}
                onClick={() => setGrade(g)}
              >
                {g}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="safe-bottom sticky bottom-0 -mx-4 mt-auto bg-gradient-to-t from-bg via-bg to-bg/0 px-4 pt-6">
          <button className="btn btn-primary btn-xl" disabled={!canSubmit}>
            {canSubmit ? `✨ ${t("learn.submit")}` : t("learn.need_input")}
          </button>
        </div>
      </form>
    </Page>
  );
}

export default function LearnPage() {
  return (
    <RequireStudent>
      <LearnForm />
    </RequireStudent>
  );
}
