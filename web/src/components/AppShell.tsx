"use client";

/* Каркас сайта: навигация по роли и «характер» раздела.
   Телефон — нижняя панель вкладок, компьютер (lg) — боковое меню с логотипом.
   На экранах-«фокусах» (урок, тест, дуэль, вход) навигации нет, чтобы ничего не отвлекало.
   На <html> ставятся data-section (game / shop / exam / learn) и data-audience (adult),
   data-age (junior — 5–7 класс) — по ним globals.css меняет оформление. */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useOptionalAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { applyAge, applySettings } from "@/lib/settings";
import type { Me } from "@/lib/types";

type Item = { href: string; icon: string; key: string; desktopOnly?: boolean };

const NAV: Record<NonNullable<Me["role"]>, Item[]> = {
  student: [
    { href: "/", icon: "🏠", key: "home" },
    { href: "/learn", icon: "📚", key: "learn" },
    { href: "/duels", icon: "⚔️", key: "duels" },
    { href: "/avatar", icon: "🦏", key: "avatar" },
    { href: "/profile", icon: "⚙️", key: "profile" },
  ],
  parent: [
    { href: "/parent", icon: "🏠", key: "cabinet" },
    { href: "/journal", icon: "📒", key: "journal" },
    { href: "/family", icon: "👨‍👩‍👧", key: "family" },
    { href: "/support", icon: "💬", key: "support" },
    { href: "/profile", icon: "⚙️", key: "profile" },
  ],
  teacher: [
    { href: "/teacher", icon: "🏠", key: "cabinet" },
    { href: "/journal", icon: "📒", key: "journal" },
    { href: "/teacher/checks", icon: "📝", key: "checks" },
    { href: "/teacher/materials", icon: "🧑‍🏫", key: "materials" },
    { href: "/support", icon: "💬", key: "support", desktopOnly: true },
    { href: "/profile", icon: "⚙️", key: "profile" },
  ],
};

/** Экраны без навигации: вход и приглашения — для всех; у ученика — любой вложенный экран
 *  (урок, тест, дуэль, сторис) и вечерний тест. */
function isFocus(path: string, role: Me["role"] | undefined): boolean {
  if (/^\/(login|privacy|family\/join|duels\/join)/.test(path)) return true;
  if (role !== "student") return false;
  return path.split("/").filter(Boolean).length >= 2 || path === "/evening";
}

function sectionOf(path: string): string {
  if (/^\/(quests|duels|stories)(\/|$)/.test(path)) return "game";
  if (/^\/avatar(\/|$)/.test(path)) return "shop";
  if (/^\/(dtm|ielts)(\/|$)/.test(path)) return "exam";
  if (/^\/(learn|tutor)(\/|$)/.test(path)) return "learn";
  return "base";
}

function isActive(path: string, href: string): boolean {
  if (href === "/" || href === "/teacher" || href === "/parent") return path === href;
  return path === href || path.startsWith(`${href}/`);
}

function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const t = useT();
  const auth = useOptionalAuth();
  const toggle = () => {
    const next = document.documentElement.dataset.theme === "night" ? "sun" : "night";
    if (auth?.me) auth.saveSettings({ theme: next }).catch(() => undefined);
    else applySettings({ theme: next }); // гость — только в этом браузере
  };
  return (
    <button
      type="button"
      onClick={toggle}
      className={
        compact
          ? "grid h-12 w-12 shrink-0 place-items-center rounded-2xl border-[length:var(--border-w)] border-line bg-surface text-xl"
          : "nav-link w-full"
      }
      aria-label={compact ? t("profile.look") : undefined}
    >
      <span className="grid h-8 w-8 place-items-center text-lg" aria-hidden="true">
        <span className="dark-only">☀️</span>
        <span className="light-only">🌙</span>
      </span>
      {!compact && (
        <span>
          <span className="light-only">{t("nav.theme_to_night")}</span>
          <span className="dark-only">{t("nav.theme_to_sun")}</span>
        </span>
      )}
    </button>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useT();
  const path = usePathname() || "/";
  const auth = useOptionalAuth();
  const me = auth?.me ?? null;
  const role = me?.role ?? null;
  const grade = me?.student?.grade ?? null;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.section = sectionOf(path);
    if (role === "parent" || role === "teacher") root.dataset.audience = "adult";
    else delete root.dataset.audience;
  }, [path, role]);

  useEffect(() => {
    if (!role) return;
    applyAge(role === "student" && grade !== null && grade <= 7 ? "junior" : "standard");
  }, [role, grade]);

  const items = role ? NAV[role] : null;
  const withNav = Boolean(items) && !isFocus(path, role);

  // Отступ под нижние вкладки даёт globals.css ([data-nav] main) — без лишней прокрутки
  useEffect(() => {
    const root = document.documentElement;
    if (withNav) root.dataset.nav = "on";
    else delete root.dataset.nav;
  }, [withNav]);

  if (!items || !withNav) return <>{children}</>;

  return (
    <>
      {/* Компьютер: боковое меню */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col gap-1 border-r-[length:var(--border-w)] border-line bg-surface/80 p-4 backdrop-blur lg:flex">
        <Link href={items[0].href} className="mb-4 flex justify-center" aria-label={t("app.name")}>
          <span className="logo h-24 w-32" aria-hidden="true" />
        </Link>
        <nav className="flex flex-col gap-1" aria-label={t("nav.menu")}>
          {items.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link" aria-current={isActive(path, item.href) ? "page" : undefined}>
              <span className="grid h-8 w-8 place-items-center text-xl" aria-hidden="true">{item.icon}</span>
              <span>{t(`nav.${item.key}`)}</span>
            </Link>
          ))}
        </nav>
        <div className="mt-auto">
          <ThemeToggle />
        </div>
      </aside>

      <div className="lg:pl-64">{children}</div>

      {/* Телефон: нижние вкладки */}
      <nav
        className="safe-bottom fixed inset-x-0 bottom-0 z-30 border-t-[length:var(--border-w)] border-line bg-surface/90 px-2 pt-1.5 backdrop-blur lg:hidden"
        aria-label={t("nav.menu")}
      >
        <div className="mx-auto flex max-w-app gap-1">
          {items
            .filter((item) => !item.desktopOnly)
            .map((item) => (
              <Link key={item.href} href={item.href} className="tab-link" aria-current={isActive(path, item.href) ? "page" : undefined}>
                <span className="tab-icon grid h-8 w-12 place-items-center rounded-xl text-xl" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="w-full truncate text-center">{t(`nav.${item.key}`)}</span>
              </Link>
            ))}
        </div>
      </nav>
    </>
  );
}

export { ThemeToggle };
