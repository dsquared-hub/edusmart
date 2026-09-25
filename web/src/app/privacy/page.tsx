"use client";

import { useEffect, useState } from "react";
import { LanguagePicker } from "@/components/LanguagePicker";
import { IconButton, Page } from "@/components/ui";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { PublicConfig } from "@/lib/types";

const SECTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

/** Политика конфиденциальности на трёх языках. Оператор, контакты и место
 *  хранения берутся из настроек сервера (.env), версия — POLICY_VERSION. */
export default function PrivacyPage() {
  const t = useT();
  const [config, setConfig] = useState<PublicConfig | null>(null);

  useEffect(() => {
    api<PublicConfig>("/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  const vars = {
    operator: config?.operator_name ?? "…",
    contact: config?.operator_contact ?? "…",
    location: config?.data_location ?? "…",
  };

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <IconButton onClick={() => history.back()} label={t("privacy.back")}>‹</IconButton>
        <div className="flex-1">
          <h1 className="text-2xl font-black leading-tight">📄 {t("privacy.title")}</h1>
          {config && (
            <p className="text-sm font-bold text-muted">{t("privacy.version", { version: config.policy_version })}</p>
          )}
        </div>
      </header>
      <LanguagePicker compact />
      <article className="card flex flex-col gap-5">
        {SECTIONS.map((n) => (
          <section key={n} className="flex flex-col gap-1">
            <h2 className="text-lg font-black">{t(`privacy.s${n}_title`)}</h2>
            <p className="font-semibold leading-relaxed">{t(`privacy.s${n}_text`, vars)}</p>
          </section>
        ))}
      </article>
    </Page>
  );
}
