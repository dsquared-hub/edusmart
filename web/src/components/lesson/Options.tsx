"use client";

const LETTERS = ["А", "Б", "В", "Г", "Д"];

export type OptionState = "idle" | "correct" | "wrong" | "dim";

export function Options({
  options,
  states,
  disabled,
  onPick,
  shakeIndex,
}: {
  options: string[];
  states: OptionState[];
  disabled: boolean;
  onPick: (index: number) => void;
  shakeIndex: number | null;
}) {
  return (
    <div className="flex flex-col gap-3" role="group">
      {options.map((option, i) => {
        const state = states[i] ?? "idle";
        return (
          <button
            key={i}
            type="button"
            className={`option ${state === "correct" ? "anim-pop" : ""} ${shakeIndex === i ? "anim-shake" : ""} ${state === "dim" ? "opacity-50" : ""}`}
            data-state={state}
            disabled={disabled}
            onClick={() => onPick(i)}
          >
            <span className="option-letter" aria-hidden="true">
              {state === "correct" ? "✓" : state === "wrong" ? "✕" : LETTERS[i] ?? i + 1}
            </span>
            <span className="flex-1">{option}</span>
          </button>
        );
      })}
    </div>
  );
}
