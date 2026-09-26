import type { UserSettings } from "./types";

// Настройки хранятся в профиле на сервере; localStorage — только кэш,
// чтобы тема применялась до загрузки профиля (без мигания цветов).
export const SETTINGS_CACHE_KEY = "edu.settings";
/** Возрастная группа ученика (шрифт): кэш, чтобы не мигал шрифт при загрузке */
export const AGE_CACHE_KEY = "edu.age";

export function applySettings(settings: Partial<UserSettings>) {
  const root = document.documentElement;
  if (settings.theme) root.dataset.theme = settings.theme === "night" ? "night" : "sun";
  if (settings.high_contrast !== undefined) root.dataset.contrast = settings.high_contrast ? "high" : "normal";
  if (settings.dyslexia_font !== undefined) root.dataset.font = settings.dyslexia_font ? "readable" : "default";
  if (settings.lang) root.lang = settings.lang;
  try {
    const cached = JSON.parse(localStorage.getItem(SETTINGS_CACHE_KEY) || "{}");
    localStorage.setItem(SETTINGS_CACHE_KEY, JSON.stringify({ ...cached, ...settings }));
  } catch {
    /* приватный режим — просто не кэшируем */
  }
}

/** 5–7 класс — «junior» (круглый шрифт), остальные — «standard». */
export function applyAge(age: "junior" | "standard") {
  document.documentElement.dataset.age = age;
  try {
    localStorage.setItem(AGE_CACHE_KEY, age);
  } catch {
    /* не кэшируем */
  }
}

// Выполняется в <head> до отрисовки страницы. Без сохранённой темы — как в системе.
export const SETTINGS_BOOT_SCRIPT = `(function(){var r=document.documentElement;try{var s=JSON.parse(localStorage.getItem("${SETTINGS_CACHE_KEY}")||"{}");var t=s.theme;if(!t&&window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches)t="night";r.dataset.theme=t==="night"?"night":"sun";r.dataset.contrast=s.high_contrast?"high":"normal";r.dataset.font=s.dyslexia_font?"readable":"default";r.dataset.age=localStorage.getItem("${AGE_CACHE_KEY}")||"standard";}catch(e){}})();`;
