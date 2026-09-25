"use client";

/* Общие элементы Academic Copilot: статус пакета и уровень уверенности ИИ. */
import { useT } from "@/lib/i18n";
import type { CheckStatus, ReviewLevel } from "@/lib/types";

export function StatusBadge({ status }: { status: CheckStatus }) {
  const t = useT();
  const tone: Record<CheckStatus, string> = {
    queued: "bg-line text-ink",
    processing: "bg-accent/25 text-ink",
    review: "bg-primary/20 text-ink",
    confirmed: "bg-good/15 text-good",
    failed: "bg-bad/15 text-bad",
  };
  return <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-extrabold ${tone[status]}`}>{t(`checks.status.${status}`)}</span>;
}

/** Уверенность ИИ: ≥90 — зелёный (в 1 клик), 70–89 — жёлтый «Проверьте», ниже — вручную.
 *  Цвет дублируется значком и текстом — не полагаемся только на цвет. */
export function LevelBadge({ level, confidence }: { level: ReviewLevel | null; confidence: number | null }) {
  const t = useT();
  if (!level) return null;
  const style: Record<ReviewLevel, string> = {
    one_click: "bg-good/15 text-good",
    review: "bg-accent/30 text-ink",
    manual: "bg-bad/15 text-bad",
  };
  const icon: Record<ReviewLevel, string> = { one_click: "✅", review: "🟡", manual: "✍️" };
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-extrabold ${style[level]}`}>
      {icon[level]} {confidence !== null ? `${confidence}% · ` : ""}
      {t(`checks.level.${level}`)}
    </span>
  );
}

export const MARK_COLORS: Record<string, string> = {
  calculation: "#e8544c",
  formula: "#b04fd6",
  logic: "#f08a24",
  spelling: "#2f7fd6",
  other: "#6b7280",
};
