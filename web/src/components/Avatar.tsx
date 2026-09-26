"use client";

/* Персонаж ученика — носорог, который растёт с уровнем и носит купленные вещи.
   Рисуется слоями в одном SVG: фон → вещи за спиной → тело → одежда → голова →
   очки → шапка → вещи спереди. Координаты вещей привязаны к базовой фигуре,
   а рост — это общий масштаб от ног, поэтому вещи всегда сидят на месте. */
import { useId } from "react";

export type Equipped = Partial<Record<"hat" | "outfit" | "glasses" | "extra" | "background", string>>;
export type Stage = "baby" | "kid" | "teen" | "champion";

const SCALE: Record<Stage, number> = { baby: 0.7, kid: 0.82, teen: 0.93, champion: 1 };
const HORN: Record<Stage, number> = { baby: 12, kid: 20, teen: 27, champion: 32 };

const SKIN = "#9aa6bb";
const SKIN_DARK = "#7d889c";
const SNOUT = "#c5ccd8";
const INK = "#2b2d42";

function Background({ code }: { code?: string }) {
  switch (code) {
    case "park":
      return (
        <g>
          <rect width="200" height="220" fill="#bfe6ff" />
          <circle cx="165" cy="35" r="16" fill="#ffd166" />
          <ellipse cx="100" cy="225" rx="150" ry="55" fill="#7cc576" />
          <rect x="22" y="120" width="8" height="40" fill="#8b5a2b" />
          <circle cx="26" cy="112" r="20" fill="#4caf50" />
        </g>
      );
    case "sea":
      return (
        <g>
          <rect width="200" height="220" fill="#aee2ff" />
          <circle cx="40" cy="40" r="15" fill="#ffd166" />
          <rect y="150" width="200" height="70" fill="#3fa7d6" />
          <path d="M0 150 q12 -8 25 0 t25 0 t25 0 t25 0 t25 0 t25 0 t25 0 t25 0" fill="none" stroke="#e8f7ff" strokeWidth="4" />
          <rect y="195" width="200" height="25" fill="#f4d58d" />
        </g>
      );
    case "classroom":
      return (
        <g>
          <rect width="200" height="220" fill="#f6e7c8" />
          <rect x="25" y="18" width="150" height="70" rx="4" fill="#2f6b4f" stroke="#8b5a2b" strokeWidth="5" />
          <text x="100" y="62" textAnchor="middle" fontSize="22" fontWeight="900" fill="#e8f5e9">
            2+2=4
          </text>
          <rect y="185" width="200" height="35" fill="#c89f6d" />
        </g>
      );
    case "space":
      return (
        <g>
          <rect width="200" height="220" fill="#1b1f3b" />
          {[
            [20, 25], [60, 15], [150, 30], [180, 70], [30, 90], [170, 140], [15, 170], [120, 12],
          ].map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="2" fill="#fff" />
          ))}
          <circle cx="160" cy="45" r="18" fill="#f28c38" />
          <ellipse cx="160" cy="45" rx="28" ry="6" fill="none" stroke="#ffd6a5" strokeWidth="3" />
        </g>
      );
    default:
      return <circle cx="100" cy="112" r="96" fill="rgb(var(--soft))" />;
  }
}

/** Вещи за спиной: плащ, рюкзак */
function ExtraBehind({ code }: { code?: string }) {
  if (code === "cape")
    return <path d="M66 118 L134 118 L156 200 Q100 212 44 200 Z" fill="#d62839" />;
  if (code === "backpack")
    return <rect x="126" y="122" width="30" height="46" rx="9" fill="#f4a261" stroke="#c9733a" strokeWidth="3" />;
  return null;
}

function Outfit({ code }: { code?: string }) {
  switch (code) {
    case "tshirt":
      return (
        <g>
          <rect x="50" y="108" width="100" height="62" fill="#ef476f" />
          <circle cx="100" cy="140" r="9" fill="#ffd166" />
        </g>
      );
    case "hoodie":
      return (
        <g>
          <rect x="50" y="108" width="100" height="84" fill="#2a9d8f" />
          <rect x="78" y="156" width="44" height="18" rx="6" fill="#23867a" />
          <path d="M92 118 v16 M108 118 v16" stroke="#e9f5f3" strokeWidth="3" strokeLinecap="round" />
        </g>
      );
    case "school_uniform":
      return (
        <g>
          <rect x="50" y="108" width="100" height="84" fill="#264478" />
          <path d="M84 110 L100 146 L116 110 Z" fill="#fff" />
          <path d="M100 116 l-5 8 l5 24 l5 -24 Z" fill="#d62839" />
        </g>
      );
    case "tuxedo":
      return (
        <g>
          <rect x="50" y="108" width="100" height="84" fill="#1f2230" />
          <path d="M82 110 L100 160 L118 110 Z" fill="#fff" />
          <path d="M90 118 L100 123 L110 118 L110 128 L100 123 L90 128 Z" fill="#d62839" />
          <circle cx="100" cy="138" r="2.5" fill={INK} />
          <circle cx="100" cy="148" r="2.5" fill={INK} />
        </g>
      );
    case "superhero":
      return (
        <g>
          <rect x="50" y="108" width="100" height="84" fill="#3a86ff" />
          <rect x="50" y="170" width="100" height="8" fill="#ffd166" />
          <path d="M100 124 l6 12 l13 2 l-10 9 l3 13 l-12 -7 l-12 7 l3 -13 l-10 -9 l13 -2 Z" fill="#d62839" stroke="#ffd166" strokeWidth="2" />
        </g>
      );
    case "astronaut":
      return (
        <g>
          <rect x="50" y="108" width="100" height="84" fill="#f1f3f5" />
          <rect x="82" y="128" width="36" height="26" rx="4" fill="#adb5bd" />
          <circle cx="92" cy="141" r="4" fill="#ef476f" />
          <circle cx="108" cy="141" r="4" fill="#06d6a0" />
          <rect x="50" y="176" width="100" height="6" fill="#f28c38" />
        </g>
      );
    case "knight":
      return (
        <g>
          <rect x="50" y="108" width="100" height="84" fill="#adb5bd" />
          <path d="M50 132 H150 M50 156 H150 M100 108 V192" stroke="#6c757d" strokeWidth="3" />
          <path d="M86 124 h28 v18 q-14 14 -28 0 Z" fill="#d62839" stroke="#ffd166" strokeWidth="2" />
        </g>
      );
    default:
      return null;
  }
}

function Glasses({ code }: { code?: string }) {
  if (code === "round_glasses")
    return (
      <g fill="none" stroke={INK} strokeWidth="3">
        <circle cx="80" cy="78" r="11" />
        <circle cx="120" cy="78" r="11" />
        <path d="M91 78 h18" />
      </g>
    );
  if (code === "sunglasses")
    return (
      <g fill="#1f2230">
        <rect x="66" y="70" width="28" height="17" rx="7" />
        <rect x="106" y="70" width="28" height="17" rx="7" />
        <rect x="92" y="74" width="16" height="3" />
      </g>
    );
  if (code === "star_glasses") {
    const star = (cx: number) =>
      `M${cx} 64 l4 9 l10 1 l-8 7 l3 10 l-9 -5 l-9 5 l3 -10 l-8 -7 l10 -1 Z`;
    return (
      <g fill="#ff70a6" stroke="#c9184a" strokeWidth="2" strokeLinejoin="round">
        <path d={star(80)} />
        <path d={star(120)} />
        <path d="M92 76 h16" fill="none" />
      </g>
    );
  }
  return null;
}

function Hat({ code }: { code?: string }) {
  switch (code) {
    case "cap":
      return (
        <g>
          <path d="M60 52 Q100 6 140 52 Z" fill="#ef476f" />
          <path d="M100 52 H160 Q156 60 140 60 H100 Z" fill="#c9184a" />
          <circle cx="100" cy="26" r="4" fill="#c9184a" />
        </g>
      );
    case "headphones":
      return (
        <g>
          <path d="M52 70 Q52 18 100 18 Q148 18 148 70" fill="none" stroke="#3a0ca3" strokeWidth="7" />
          <rect x="42" y="60" width="18" height="28" rx="7" fill="#7209b7" />
          <rect x="140" y="60" width="18" height="28" rx="7" fill="#7209b7" />
        </g>
      );
    case "wizard_hat":
      return (
        <g>
          <path d="M100 -18 L136 50 H64 Z" fill="#5a189a" />
          <ellipse cx="100" cy="50" rx="46" ry="8" fill="#3c096c" />
          <circle cx="94" cy="22" r="3" fill="#ffd166" />
          <circle cx="108" cy="34" r="2.5" fill="#ffd166" />
          <circle cx="100" cy="6" r="2" fill="#ffd166" />
        </g>
      );
    case "grad_cap":
      return (
        <g>
          <rect x="72" y="34" width="56" height="16" fill="#1f2230" />
          <path d="M100 16 L150 30 L100 44 L50 30 Z" fill="#2b2d42" />
          <path d="M140 30 V52" stroke="#ffd166" strokeWidth="3" />
          <circle cx="140" cy="54" r="4" fill="#ffd166" />
        </g>
      );
    case "crown":
      return (
        <g>
          <path d="M68 50 L68 20 L84 34 L100 12 L116 34 L132 20 L132 50 Z" fill="#ffd166" stroke="#e09f3e" strokeWidth="3" strokeLinejoin="round" />
          <circle cx="100" cy="38" r="4" fill="#ef476f" />
        </g>
      );
    default:
      return null;
  }
}

/** Вещи спереди: шарф, медаль */
function ExtraFront({ code }: { code?: string }) {
  if (code === "scarf")
    return (
      <g>
        <rect x="62" y="112" width="76" height="14" rx="7" fill="#e63946" />
        <rect x="112" y="118" width="13" height="30" rx="5" fill="#c1121f" />
      </g>
    );
  if (code === "medal")
    return (
      <g>
        <path d="M86 112 L100 140 L114 112" fill="none" stroke="#3a86ff" strokeWidth="6" />
        <circle cx="100" cy="146" r="11" fill="#ffd166" stroke="#e09f3e" strokeWidth="3" />
        <text x="100" y="151" textAnchor="middle" fontSize="12" fontWeight="900" fill="#9c6644">
          1
        </text>
      </g>
    );
  if (code === "backpack")
    return <path d="M126 116 V160" stroke="#c9733a" strokeWidth="5" strokeLinecap="round" />;
  return null;
}

export function Avatar({
  stage,
  equipped,
  size = 220,
  className = "",
  label,
}: {
  stage: Stage;
  equipped: Equipped;
  size?: number;
  className?: string;
  label?: string;
}) {
  const id = `avatar${useId().replace(/[^a-zA-Z0-9]/g, "")}`; // «:r1:» не годится для url(#…)
  const frame = `${id}-frame`;
  const torso = `${id}-torso`;
  const s = SCALE[stage];
  const horn = HORN[stage];
  return (
    <svg
      viewBox="0 0 200 220"
      width={size}
      height={size * 1.1}
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <clipPath id={frame}>
          <rect width="200" height="220" rx="28" />
        </clipPath>
        <clipPath id={torso}>
          <ellipse cx="100" cy="150" rx="44" ry="42" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${frame})`}>
        <Background code={equipped.background} />
        <ellipse cx="100" cy="206" rx={46 * s} ry="7" fill="rgb(0 0 0 / 0.15)" />
        {/* рост — масштаб от ног: вещи остаются на своих местах */}
        <g transform={`translate(100 205) scale(${s}) translate(-100 -205)`}>
          <ExtraBehind code={equipped.extra} />
          {/* ноги и руки */}
          <rect x="70" y="170" width="24" height="34" rx="10" fill={SKIN_DARK} />
          <rect x="106" y="170" width="24" height="34" rx="10" fill={SKIN_DARK} />
          <ellipse cx="55" cy="150" rx="11" ry="22" fill={SKIN_DARK} />
          <ellipse cx="145" cy="150" rx="11" ry="22" fill={SKIN_DARK} />
          {/* тело и одежда по его форме */}
          <ellipse cx="100" cy="150" rx="44" ry="42" fill={SKIN} />
          <g clipPath={`url(#${torso})`}>
            <Outfit code={equipped.outfit} />
          </g>
          {/* голова */}
          <ellipse cx="64" cy="50" rx="10" ry="15" transform="rotate(-25 64 50)" fill={SKIN_DARK} />
          <ellipse cx="136" cy="50" rx="10" ry="15" transform="rotate(25 136 50)" fill={SKIN_DARK} />
          <ellipse cx="100" cy="84" rx="48" ry="40" fill={SKIN} />
          <ellipse cx="100" cy="106" rx="30" ry="17" fill={SNOUT} />
          <path d={`M90 97 Q100 ${97 - horn * 1.3} 104 ${95 - horn} Q108 ${97 - horn * 0.4} 110 97 Z`} fill="#f1e3c8" stroke="#d9c7a2" strokeWidth="1.5" />
          <circle cx="80" cy="78" r="6" fill={INK} />
          <circle cx="120" cy="78" r="6" fill={INK} />
          <circle cx="82" cy="76" r="2" fill="#fff" />
          <circle cx="122" cy="76" r="2" fill="#fff" />
          <ellipse cx="92" cy="108" rx="3" ry="2" fill={SKIN_DARK} />
          <ellipse cx="108" cy="108" rx="3" ry="2" fill={SKIN_DARK} />
          <path d="M90 115 Q100 122 110 115" fill="none" stroke={INK} strokeWidth="2.5" strokeLinecap="round" />
          <ellipse cx="70" cy="96" rx="7" ry="4" fill="#f4a6b8" opacity="0.6" />
          <ellipse cx="130" cy="96" rx="7" ry="4" fill="#f4a6b8" opacity="0.6" />
          <Glasses code={equipped.glasses} />
          <Hat code={equipped.hat} />
          <ExtraFront code={equipped.extra} />
        </g>
        {stage === "champion" && (
          <g fill="#ffd166">
            <path d="M22 60 l3 7 l7 3 l-7 3 l-3 7 l-3 -7 l-7 -3 l7 -3 Z" />
            <path d="M176 96 l2.5 6 l6 2.5 l-6 2.5 l-2.5 6 l-2.5 -6 l-6 -2.5 l6 -2.5 Z" />
          </g>
        )}
      </g>
    </svg>
  );
}
