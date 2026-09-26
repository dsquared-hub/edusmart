"use client";

/* Старт секции IELTS по ссылке из хаба: создаёт (или продолжает) попытку и открывает её. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Thinking } from "@/components/Thinking";
import { Notice, Page } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { IeltsAttempt } from "@/lib/types";

function Starter({ path, body }: { path: string; body: Record<string, unknown> }) {
  const t = useT();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(body);

  useEffect(() => {
    api<IeltsAttempt>(path, { method: "POST", json: JSON.parse(key) })
      .then((a) => router.replace(`/ielts/${a.id}`))
      .catch((e) => setError(errorCode(e)));
  }, [path, key, router]);

  if (!error) return <Thinking title={t("ielts.preparing")} />;
  return (
    <Page className="justify-center gap-4">
      <Notice tone="error">{t(`errors.${error}`)}</Notice>
      <Link href="/ielts" className="btn btn-soft">‹ IELTS</Link>
    </Page>
  );
}

export function StartSection({ path, body }: { path: string; body: Record<string, unknown> }) {
  return (
    <RequireStudent>
      <Starter path={path} body={body} />
    </RequireStudent>
  );
}
