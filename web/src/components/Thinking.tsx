"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import { Mascot } from "./Mascot";
import { Dots } from "./ui";

/** Экран ожидания, пока модель готовит объяснение: носорог думает, подсказки меняются. */
export function Thinking({ title }: { title?: string }) {
  const t = useT();
  const tips = t.list("learn.tips");
  const [tip, setTip] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTip((i) => (i + 1) % Math.max(1, tips.length)), 2200);
    return () => clearInterval(id);
  }, [tips.length]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-bg/95 px-6 backdrop-blur-sm"
      role="status"
      aria-live="polite"
    >
      <div className="flex max-w-sm flex-col items-center gap-5 text-center">
        <Mascot mood="thinking" size={140} className="anim-bob" />
        <h2 className="text-2xl font-black">{title ?? t("learn.thinking_title")}</h2>
        <Dots />
        {tips.length > 0 && (
          <p key={tip} className="min-h-[3rem] text-lg font-bold text-muted anim-rise">
            {tips[tip]}
          </p>
        )}
      </div>
    </div>
  );
}
