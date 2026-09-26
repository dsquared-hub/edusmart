"use client";

/* IELTS AI Coach (10–11 классы): четыре секции, лучшие Band Score и история попыток. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { IeltsAttempt, IeltsOverview } from "@/lib/types";

const SECTIONS = [
  { key: "reading", icon: "📖", href: "/ielts/reading" },
  { key: "listening", icon: "🎧", href: "/ielts/listening" },
  { key: "writing", icon: "✍️", href: null },
  { key: "speaking", icon: "🗣️", href: "/ielts/speaking" },
] as const;

function Hub() {
  const t = useT();
  const router = useRouter();
  const [data, setData] = useState<IeltsOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<IeltsOverview>("/ielts").then(setData).catch((e) => setError(errorCode(e)));
  }, []);

  if (!data && !error) return <Splash />;
  const tooYoung = !!data && data.grade !== null && data.grade < data.min_grade;

  const writing = async (task: 1 | 2) => {
    setBusy(true);
    setError(null);
    try {
      const attempt = await api<IeltsAttempt>("/ielts/writing", { method: "POST", json: { task } });
      router.push(`/ielts/${attempt.id}`);
    } catch (e) {
      setError(errorCode(e));
      setBusy(false);
    }
  };

  return (
    <Page className="gap-5">
      {busy && <Thinking title={t("ielts.preparing")} />}
      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">🇬🇧 {t("ielts.title")}</h1>
      </header>
      <p className="font-bold text-muted">{t("ielts.intro")}</p>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}
      {tooYoung && <Notice>{t("ielts.too_young", { grade: data!.min_grade })}</Notice>}

      {!tooYoung && (
        <div className="grid grid-cols-2 gap-3">
          {SECTIONS.map((s) => {
            const best = data?.best[s.key];
            const body = (
              <>
                <span className="text-4xl" aria-hidden="true">{s.icon}</span>
                <span className="text-lg font-black">{t(`ielts.section.${s.key}`)}</span>
                <span className="text-sm font-bold text-muted">
                  {best !== undefined ? t("ielts.best", { band: best.toFixed(1) }) : t(`ielts.hint.${s.key}`)}
                </span>
              </>
            );
            return s.href ? (
              <Link key={s.key} href={s.href} className="card flex flex-col items-center gap-1 text-center anim-rise">{body}</Link>
            ) : (
              <div key={s.key} className="card flex flex-col items-center gap-2 text-center anim-rise">
                {body}
                <div className="grid w-full grid-cols-2 gap-2">
                  <button type="button" className="btn btn-soft !min-h-[2.5rem] text-sm" onClick={() => writing(1)} disabled={busy}>Task 1</button>
                  <button type="button" className="btn btn-soft !min-h-[2.5rem] text-sm" onClick={() => writing(2)} disabled={busy}>Task 2</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {data && data.attempts.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="label">{t("ielts.history")}</h2>
          {data.attempts.map((a) => (
            <Link key={a.id} href={`/ielts/${a.id}`} className="option">
              <span className="text-3xl" aria-hidden="true">{SECTIONS.find((s) => a.kind.startsWith(s.key))?.icon ?? "🇬🇧"}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate">{t(`ielts.kind.${a.kind}`)}</span>
                <span className="text-sm font-bold text-muted">
                  {new Date(a.started_at).toLocaleDateString()} · {a.status === "done" && a.band !== null ? `Band ${a.band.toFixed(1)}` : t("ielts.in_progress")}
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

export default function IeltsPage() {
  return (
    <RequireStudent>
      <Hub />
    </RequireStudent>
  );
}
