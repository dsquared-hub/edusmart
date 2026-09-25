import type { UserSettings } from "./types";

// Настройки хранятся в профиле на сервере; localStorage — только кэш,
// чтобы тема применялась до загрузки профиля (без мигания цветов).
export const SETTINGS_CACHE_KEY = "edu.settings";

export function applySettings(settings: Partial<UserSettings>) {
  const root = document.documentElement;
  if (settings.theme) root.dataset.theme = settings.theme;
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

// Выполняется в <head> до отрисовки страницы.
export const SETTINGS_BOOT_SCRIPT = `(function(){try{var s=JSON.parse(localStorage.getItem("${SETTINGS_CACHE_KEY}")||"{}");var r=document.documentElement;if(s.theme)r.dataset.theme=s.theme;r.dataset.contrast=s.high_contrast?"high":"normal";r.dataset.font=s.dyslexia_font?"readable":"default";}catch(e){}})();`;
