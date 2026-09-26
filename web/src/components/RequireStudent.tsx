"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { Mascot } from "./Mascot";
import { Page, Splash } from "./ui";

const isAdult = (role: string | null | undefined) => role === "parent" || role === "teacher";

/** Страницы учеников: гость → /login, родитель/учитель → журнал результатов,
 *  без роли — подсказка. */
export function RequireStudent({ children }: { children: ReactNode }) {
  const { status, me } = useAuth();
  const router = useRouter();
  const t = useT();

  useEffect(() => {
    if (status === "guest") {
      const next = window.location.pathname + window.location.search;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    } else if (status === "authed" && isAdult(me?.role)) {
      router.replace("/journal");
    }
  }, [status, me, router]);

  if (status !== "authed" || !me || isAdult(me.role)) return <Splash />;

  if (me.role !== "student") {
    return (
      <Page className="justify-center">
        <div className="card flex flex-col items-center gap-4 text-center">
          <Mascot size={96} />
          <h1 className="text-2xl font-black">{t("home.not_student_title")}</h1>
          <p className="text-muted">{t("home.not_student_text")}</p>
          <a className="btn btn-primary" href="/profile">
            ⚙️ {t("profile.title")}
          </a>
        </div>
      </Page>
    );
  }
  return <>{children}</>;
}
