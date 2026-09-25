"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useT } from "@/lib/i18n";
import { Mascot } from "./Mascot";

export function Page({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <main className={`mx-auto flex min-h-[100dvh] w-full max-w-app flex-col px-4 pb-8 pt-4 ${className}`}>{children}</main>;
}

export function Splash() {
  const t = useT();
  return (
    <div className="grid min-h-[100dvh] place-items-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <Mascot mood="thinking" size={88} className="anim-bob" />
        <Dots />
        <span className="sr-only">{t("app.loading")}</span>
      </div>
    </div>
  );
}

export function Dots() {
  return (
    <span className="inline-flex gap-1.5" aria-hidden="true">
      <span className="dot h-3 w-3 rounded-full bg-primary" />
      <span className="dot h-3 w-3 rounded-full bg-primary" />
      <span className="dot h-3 w-3 rounded-full bg-primary" />
    </span>
  );
}

export function ProgressBar({ value, total, label }: { value: number; total: number; label?: string }) {
  // Сегменты — по одному на шаг: наглядно «сколько осталось»
  return (
    <div className="flex w-full flex-col gap-1.5">
      <div
        className="flex w-full gap-1.5"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={value}
        aria-label={label}
      >
        {Array.from({ length: total }, (_, i) => (
          <div key={i} className="h-3.5 flex-1 overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: i < value ? "100%" : "0%" }}
            />
          </div>
        ))}
      </div>
      {label && <div className="text-sm font-extrabold text-muted">{label}</div>}
    </div>
  );
}

export function IconButton({
  href,
  onClick,
  label,
  children,
}: {
  href?: string;
  onClick?: () => void;
  label: string;
  children: ReactNode;
}) {
  const cls =
    "grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-surface text-2xl font-black text-ink border-[length:var(--border-w)] border-line";
  if (href) {
    return (
      <Link href={href} className={cls} aria-label={label} title={label}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls} aria-label={label} title={label}>
      {children}
    </button>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error"; children: ReactNode }) {
  const toneCls = tone === "error" ? "border-bad bg-bad/10" : "border-accent bg-accent/15";
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-2xl border-[length:var(--border-w)] px-4 py-3 font-bold ${toneCls}`}>
      {children}
    </div>
  );
}
