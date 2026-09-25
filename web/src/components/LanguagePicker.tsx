"use client";

import { LANGUAGES, useSetLang, useT } from "@/lib/i18n";

/** Выбор языка: крупные «чипы» с флагами. compact — для страницы входа. */
export function LanguagePicker({ compact = false }: { compact?: boolean }) {
  const t = useT();
  const setLang = useSetLang();
  return (
    <div
      className={`flex flex-wrap gap-2 ${compact ? "justify-center" : ""}`}
      role="radiogroup"
      aria-label={t("profile.language")}
    >
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          type="button"
          role="radio"
          aria-checked={t.lang === lang.code}
          aria-pressed={t.lang === lang.code}
          lang={lang.code}
          className={`chip ${compact ? "min-h-[2.5rem] px-3 text-sm" : ""}`}
          onClick={() => setLang(lang.code)}
        >
          <span aria-hidden="true">{lang.flag}</span>
          {lang.name}
        </button>
      ))}
    </div>
  );
}
