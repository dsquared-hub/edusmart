"use client";

import { useState } from "react";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** «⚠️ Здесь ошибка» — жалоба уходит учителю и владельцу, чтобы проверить шаг. */
export function ReportButton({
  topicId,
  index,
  kind = "step",
}: {
  topicId: number;
  index: number;
  kind?: "step" | "practice";
}) {
  const t = useT();
  const [state, setState] = useState<"idle" | "sending" | "done" | "already" | "error">("idle");
  const [error, setError] = useState("");

  const send = async () => {
    setState("sending");
    try {
      const r = await api<{ already_reported: boolean }>(`/explain/${topicId}/report`, {
        method: "POST",
        json: { step: index, kind },
      });
      setState(r.already_reported ? "already" : "done");
    } catch (e) {
      setError(t(`errors.${errorCode(e)}`));
      setState("error");
    }
  };

  if (state === "done" || state === "already") {
    return (
      <p role="status" className="text-center text-sm font-bold text-muted">
        {t(state === "done" ? "step.report_done" : "step.report_already")}
      </p>
    );
  }
  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={send}
        disabled={state === "sending"}
        className="rounded-full px-4 py-2 text-sm font-extrabold text-muted underline-offset-4 hover:underline disabled:opacity-50"
      >
        {t("step.report")}
      </button>
      {state === "error" && <p role="alert" className="text-sm font-bold text-bad">{error}</p>}
    </div>
  );
}
