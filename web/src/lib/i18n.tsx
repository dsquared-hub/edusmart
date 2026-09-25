"use client";

// Переводы: messages/<lang>.json. Новый язык — положить JSON рядом и добавить в DICTS и LANGUAGES.
import { createContext, useContext, useMemo, type ReactNode } from "react";
import en from "@messages/en.json";
import ru from "@messages/ru.json";
import uz from "@messages/uz.json";

type Dict = typeof ru;
const DICTS: Record<string, Dict> = { ru, uz, en };

export type Lang = "ru" | "uz" | "en";
/** Названия — так, как их пишут сами носители языка. */
export const LANGUAGES: { code: Lang; name: string; flag: string }[] = [
  { code: "ru", name: "Русский", flag: "🇷🇺" },
  { code: "uz", name: "Oʻzbekcha", flag: "🇺🇿" },
  { code: "en", name: "English", flag: "🇬🇧" },
];

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && value in DICTS;
}

function lookup(dict: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>(
    (node, part) => (node && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined),
    dict,
  );
}

function format(template: string, vars?: Record<string, string | number>) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) => (name in vars ? String(vars[name]) : `{${name}}`));
}

export type T = {
  (key: string, vars?: Record<string, string | number>): string;
  list: (key: string) => string[];
  lang: Lang;
};

function makeT(lang: Lang): T {
  const dict = DICTS[lang] ?? ru;
  // Нет ключа в выбранном языке — берём русский, чтобы не показывать «сырой» ключ
  const t = ((key: string, vars?: Record<string, string | number>) => {
    const value = lookup(dict, key) ?? lookup(ru, key);
    return typeof value === "string" ? format(value, vars) : key;
  }) as T;
  t.list = (key: string) => {
    const value = lookup(dict, key) ?? lookup(ru, key);
    return Array.isArray(value) ? (value as string[]) : [];
  };
  t.lang = lang;
  return t;
}

type I18nValue = { t: T; setLang: (lang: Lang) => void };

const I18nContext = createContext<I18nValue>({ t: makeT("ru"), setLang: () => undefined });

export function I18nProvider({
  lang,
  setLang,
  children,
}: {
  lang: Lang;
  setLang: (lang: Lang) => void;
  children: ReactNode;
}) {
  const value = useMemo(() => ({ t: makeT(lang), setLang }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useT(): T {
  return useContext(I18nContext).t;
}

export function useSetLang(): (lang: Lang) => void {
  return useContext(I18nContext).setLang;
}
