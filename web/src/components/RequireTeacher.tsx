"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { Mascot } from "./Mascot";
import { Page, Splash } from "./ui";

/** Страницы учителя (Academic Copilot): гость → вход ментора, остальные роли — подсказка. */
export function RequireTeacher({ children }: { children: ReactNode }) {
  const { status, me } = useAuth();
  const router = useRouter();
  const t = useT();

  useEffect(() => {
    if (status === "guest") {
      const next = window.location.pathname + window.location.search;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    }
  }, [status, router]);

  if (status !== "authed" || !me) return <Splash />;
  if (me.role !== "teacher") {
    return (
      <Page className="justify-center">
        <div className="card flex flex-col items-center gap-4 text-center">
          <Mascot size={96} />
          <h1 className="text-2xl font-black">{t("checks.title")}</h1>
          <p className="text-muted">{t("errors.not_teacher")}</p>
          <a className="btn btn-soft" href="/">
            ‹ {t("profile.back")}
          </a>
        </div>
      </Page>
    );
  }
  return <>{children}</>;
}
