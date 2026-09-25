"use client";

import { Component, type ReactNode } from "react";
import type { Visual as VisualData } from "@/lib/types";
import { Cards } from "./Cards";
import { Fractions } from "./Fractions";
import { NumberLine } from "./NumberLine";
import { StepArrows } from "./StepArrows";
import { TableViz } from "./TableViz";
import { obj } from "./util";

const RENDERERS = {
  number_line: NumberLine,
  fractions: Fractions,
  table: TableViz,
  arrows: StepArrows,
  cards: Cards,
} as const;

/** Если модель прислала что-то странное — показываем хотя бы подпись. */
class Guard extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export function Visual({ visual }: { visual: VisualData | null | undefined }) {
  if (!visual) return null;
  const Renderer = RENDERERS[visual.type as keyof typeof RENDERERS];
  const caption = visual.caption?.trim();
  if (!Renderer && !caption) return null;

  return (
    <figure className="flex flex-col gap-3 rounded-3xl bg-soft p-4">
      {Renderer && (
        <Guard fallback={null}>
          <Renderer data={obj(visual.data)} />
        </Guard>
      )}
      {caption && <figcaption className="text-center font-extrabold text-muted">{caption}</figcaption>}
    </figure>
  );
}
