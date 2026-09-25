"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LanguagePicker } from "@/components/LanguagePicker";
import { Mascot } from "@/components/Mascot";
import { BotLogin, TelegramWidget, telegramRedirectData } from "@/components/TelegramLogin";
import { Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import type { PublicConfig } from "@/lib/types";

const RETURN_PATH = "/mentor";

/** Отдельный вход для ментора (учителя). Бэкенд пускает сюда только ментора:
 *  новый пользователь без роли сразу становится ментором, ученик и родитель — отказ. */
export default function MentorLoginPage() {
  const t = useT();
  const router = useRouter();
  const { status, me, loginTelegram, logoutEverywhere } = useAuth();
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authed" && me?.role === "teacher") router.replace("/journal");
  }, [status, me, router]);

  useEffect(() => {
    api<PublicConfig>("/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  // Вернулись от Telegram с подписанными данными — входим как ментор и убираем их из адреса
  const onTelegram = useCallback(
    async (user: Record<string, string>) => {
      setError(null);
      try {
        await loginTelegram({ widget: user, as_role: "teacher" });
      } catch (e) {
        setError(errorCode(e));
      }
    },
    [loginTelegram],
  );

  useEffect(() => {
    if (status !== "guest") return;
    const data = telegramRedirectData();
    if (!data) return;
    window.history.replaceState(null, "", RETURN_PATH);
    onTelegram(data);
  }, [status, onTelegram]);

  if (status === "loading" || (status === "authed" && me?.role === "teacher")) return <Splash />;

  // В этом браузере уже вошли под другой ролью (ученик/родитель)
  if (status === "authed") {
    return (
      <Page className="justify-center">
        <div className="card flex flex-col items-center gap-4 text-center">
          <Mascot size={96} />
          <h1 className="text-2xl font-black">{t("mentor.other_role_title")}</h1>
          <p className="text-muted">{t("mentor.other_role_text", { name: me?.name ?? "" })}</p>
          <button type="button" className="btn btn-primary" onClick={logoutEverywhere}>
            {t("profile.logout")}
          </button>
          <a className="btn btn-soft" href="/">
            {t("mentor.continue")}
          </a>
        </div>
      </Page>
    );
  }

  const widgetAllowed = window.location.protocol === "https:";

  return (
    <Page className="justify-center gap-6">
      <LanguagePicker compact />
      <header className="flex flex-col items-center gap-3 text-center anim-rise">
        <Mascot size={96} />
        <span className="rounded-full bg-soft px-4 py-1 text-sm font-extrabold uppercase tracking-wide text-primary">
          👩‍🏫 {t("mentor.badge")}
        </span>
        <h1 className="text-3xl font-black">{t("mentor.title")}</h1>
        <p className="text-lg font-bold text-muted">{t("mentor.subtitle")}</p>
      </header>

      {error && (
        <Notice tone="error">
          {t(`errors.${error}`)}
          {error === "not_mentor" && (
            <>
              {" "}
              <a href="/login" className="underline underline-offset-4">
                {t("mentor.regular_link")}
              </a>
            </>
          )}
        </Notice>
      )}

      <section className="card flex flex-col gap-3 anim-rise" aria-labelledby="mentor-tg-title">
        <h2 id="mentor-tg-title" className="text-center text-xl font-black">
          ✈️ {t("login.telegram")}
        </h2>
        {config?.bot_username ? (
          <>
            <BotLogin onError={setError} asRole="teacher" />
            {/* Виджет работает только на HTTPS-домене, указанном боту в @BotFather → /setdomain */}
            {widgetAllowed && <TelegramWidget botUsername={config.bot_username} returnPath={RETURN_PATH} />}
          </>
        ) : (
          <p className="text-center text-muted">{t("login.widget_unavailable")}</p>
        )}
        <p className="text-center text-sm font-semibold text-muted">{t("mentor.hint")}</p>
      </section>

      <ul className="card flex flex-col gap-2 text-sm font-bold anim-rise">
        <li>📒 {t("mentor.feature_journal")}</li>
        <li>🎯 {t("mentor.feature_stats")}</li>
        <li>🔑 {t("mentor.feature_codes")}</li>
      </ul>

      <a href="/login" className="text-center text-sm font-bold text-muted underline underline-offset-4">
        {t("mentor.regular_link")}
      </a>
    </Page>
  );
}
