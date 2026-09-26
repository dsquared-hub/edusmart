"use client";

/* Попытка IELTS: экран зависит от секции (Writing / Reading / Listening / Speaking). */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Speaking } from "@/components/ielts/Speaking";
import { TestSection } from "@/components/ielts/TestSection";
import { Writing } from "@/components/ielts/Writing";
import { RequireStudent } from "@/components/RequireStudent";
import { IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { IeltsAttempt } from "@/lib/types";

function AttemptView({ id }: { id: number }) {
  const t = useT();
  const [attempt, setAttempt] = useState<IeltsAttempt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<IeltsAttempt>(`/ielts/attempts/${id}`).then(setAttempt).catch((e) => setError(errorCode(e)));
  }, [id]);

  if (!attempt) {
    return error ? (
      <Page className="justify-center gap-4">
        <Notice tone="error">{t(`errors.${error}`)}</Notice>
        <Link href="/ielts" className="btn btn-soft">‹ IELTS</Link>
      </Page>
    ) : (
      <Splash />
    );
  }

  return (
    <Page className="gap-4 lg:max-w-3xl">
      <header className="flex items-center gap-3">
        <IconButton href="/ielts" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 truncate text-2xl font-black leading-tight">{t(`ielts.kind.${attempt.kind}`)}</h1>
      </header>
      {attempt.kind.startsWith("writing") && <Writing key={attempt.status} initial={attempt} onChange={setAttempt} />}
      {(attempt.kind === "reading" || attempt.kind === "listening") && (
        <TestSection key={attempt.status} initial={attempt} onChange={setAttempt} />
      )}
      {attempt.kind === "speaking" && <Speaking initial={attempt} onChange={setAttempt} />}
    </Page>
  );
}

function Loader() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) return <Splash />;
  return <AttemptView id={id} />;
}

export default function IeltsAttemptPage() {
  return (
    <RequireStudent>
      <Loader />
    </RequireStudent>
  );
}
