/* Минимальный hash-роутер: прототип открывается как статический сайт без настройки сервера. */
import { useEffect, useState, type AnchorHTMLAttributes, type ReactNode } from "react";

export type Route = { path: string; params: string[] };

function parse(): Route {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, ...params] = raw.split("/").filter(Boolean);
  return { path: path ? `/${path}` : "/", params };
}

export function navigate(to: string) {
  if (window.location.hash !== `#${to}`) window.location.hash = to;
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => {
      setRoute(parse());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function Link({
  to,
  children,
  ...rest
}: { to: string; children: ReactNode } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a href={`#${to}`} {...rest}>
      {children}
    </a>
  );
}
