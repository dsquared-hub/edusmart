"use client";

/* Ссылка-приглашение на дуэль: /duels/join/ABC234 — принимаем вызов и открываем дуэль. */
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RequireStudent } from "@/components/RequireStudent";
import { Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { DuelView } from "@/lib/types";

function Join() {
  const t = useT();
  const router = useRouter();
  const { code } = useParams<{ code: string }>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<DuelView>("/duels/join", { method: "POST", json: { code } })
      .then((d) => router.replace(`/duels/${d.id}`))
      .catch((e) => setError(errorCode(e)));
  }, [code, router]);

  if (!error) return <Splash />;
  return (
    <Page className="justify-center gap-4">
      <Notice tone="error">{t(`errors.${error}`)}</Notice>
      <Link href="/duels" className="btn btn-soft">‹ {t("duels.title")}</Link>
    </Page>
  );
}

export default function JoinDuelPage() {
  return (
    <RequireStudent>
      <Join />
    </RequireStudent>
  );
}
