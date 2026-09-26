"use client";

// 3D-носорог (public/models/rhino.glb, ~1.6 МБ). Модель — рельеф, сделанный из картинки маскота,
// поэтому поворот ограничен ±22°: дальше видны плоские боковые стенки рельефа. Пока модель грузится — обычная картинка.
// Без WebGL, при «экономии трафика» или «меньше движения» — сразу 2D-маскот.
import { useEffect, useRef, useState, type Ref } from "react";
import { Mascot } from "./Mascot";

type ModelViewerElement = HTMLElement & { cameraOrbit: string };

const ORBIT = (yaw: number) => `${yaw.toFixed(1)}deg 85deg auto`;

function can3D(): boolean {
  if (typeof window === "undefined") return false;
  const conn = (navigator as { connection?: { saveData?: boolean } }).connection;
  if (conn?.saveData) return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

let loader: Promise<unknown> | null = null;

export function Mascot3D({ size = 160, className = "", label }: { size?: number; className?: string; label?: string }) {
  const [enabled, setEnabled] = useState(false);
  const ref = useRef<ModelViewerElement | null>(null);

  useEffect(() => {
    if (!can3D()) return;
    loader ??= import("@google/model-viewer");
    let alive = true;
    loader.then(() => alive && setEnabled(true)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  // Едва заметное медленное покачивание (±6°), пока ребёнок сам не крутит; после касания — пауза 4 секунды
  useEffect(() => {
    const el = ref.current;
    if (!enabled || !el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let pausedUntil = 0;
    const start = performance.now();
    const tick = (now: number) => {
      if (now > pausedUntil) el.cameraOrbit = ORBIT(Math.sin((now - start) / 2800) * 6);
      frame = requestAnimationFrame(tick);
    };
    const onChange = (e: Event) => {
      if ((e as CustomEvent<{ source?: string }>).detail?.source === "user-interaction") pausedUntil = performance.now() + 4000;
    };
    el.addEventListener("camera-change", onChange);
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      el.removeEventListener("camera-change", onChange);
    };
  }, [enabled]);

  const height = Math.round(size * 1.3);
  if (!enabled) {
    return (
      <span className={`inline-grid place-items-center ${className}`} style={{ width: size, height }}>
        <Mascot size={size} rhino />
      </span>
    );
  }
  return (
    <model-viewer
      ref={ref as Ref<HTMLElement>}
      src="/models/rhino.glb"
      poster="/mascot-512.webp"
      alt={label}
      camera-controls
      disable-zoom
      disable-pan
      disable-tap
      touch-action="pan-y"
      interaction-prompt="none"
      camera-orbit={ORBIT(0)}
      min-camera-orbit="-22deg 75deg auto"
      max-camera-orbit="22deg 95deg auto"
      field-of-view="28deg"
      interpolation-decay="120"
      shadow-intensity="0.7"
      shadow-softness="0.9"
      exposure="1.05"
      environment-image="neutral"
      className={`inline-block shrink-0 ${className}`}
      style={{ width: size, height, background: "transparent", ["--poster-color" as string]: "transparent" }}
    >
      {/* Своя пустая полоса загрузки вместо стандартной серой — пока грузится, виден 2D-постер */}
      <div slot="progress-bar" />
    </model-viewer>
  );
}
