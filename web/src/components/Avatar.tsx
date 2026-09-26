"use client";

/* Персонаж ученика — тот же 3D-носорог, что на странице входа (public/mascot-512.webp),
   который растёт с уровнем и носит купленные вещи. Слои в одном SVG: фон → вещи за спиной →
   носорог → перекрашенный костюм → очки → шапка → вещи спереди. Координаты вещей — в пикселях
   картинки 512×512; сверху 68 px запаса под шапки. Одежда перекрашивает серый костюм через маску
   public/mascot-suit-mask.png и режим наложения, поэтому объём и складки картинки сохраняются.
   Рост — общий масштаб от ног, поэтому вещи всегда сидят на месте. */
import { useId, type CSSProperties, type ReactNode } from "react";

export type Equipped = Partial<Record<"hat" | "outfit" | "glasses" | "extra" | "background", string>>;
export type Stage = "baby" | "kid" | "teen" | "champion";

const SCALE: Record<Stage, number> = { baby: 0.72, kid: 0.83, teen: 0.93, champion: 1 };

const W = 512;
const H = 580;
const TOP = 68; // запас над головой
const FEET = TOP + 505;
const INK = "#2b2d42";

function Background({ code }: { code?: string }) {
  // Фоны нарисованы в сетке 200×220 и растягиваются на всю рамку
  const scene = (children: ReactNode) => <g transform={`scale(${W / 200} ${H / 220})`}>{children}</g>;
  switch (code) {
    case "park":
      return scene(
        <g>
          <rect width="200" height="220" fill="#bfe6ff" />
          <circle cx="165" cy="35" r="16" fill="#ffd166" />
          <ellipse cx="100" cy="225" rx="150" ry="55" fill="#7cc576" />
          <rect x="22" y="120" width="8" height="40" fill="#8b5a2b" />
          <circle cx="26" cy="112" r="20" fill="#4caf50" />
        </g>,
      );
    case "sea":
      return scene(
        <g>
          <rect width="200" height="220" fill="#aee2ff" />
          <circle cx="40" cy="40" r="15" fill="#ffd166" />
          <rect y="150" width="200" height="70" fill="#3fa7d6" />
          <path d="M0 150 q12 -8 25 0 t25 0 t25 0 t25 0 t25 0 t25 0 t25 0 t25 0" fill="none" stroke="#e8f7ff" strokeWidth="4" />
          <rect y="195" width="200" height="25" fill="#f4d58d" />
        </g>,
      );
    case "classroom":
      return scene(
        <g>
          <rect width="200" height="220" fill="#f6e7c8" />
          <rect x="25" y="18" width="150" height="70" rx="4" fill="#2f6b4f" stroke="#8b5a2b" strokeWidth="5" />
          <text x="100" y="62" textAnchor="middle" fontSize="22" fontWeight="900" fill="#e8f5e9">
            2+2=4
          </text>
          <rect y="185" width="200" height="35" fill="#c89f6d" />
        </g>,
      );
    case "space":
      return scene(
        <g>
          <rect width="200" height="220" fill="#1b1f3b" />
          {[
            [20, 25], [60, 15], [150, 30], [180, 70], [30, 90], [170, 140], [15, 170], [120, 12],
          ].map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="2" fill="#fff" />
          ))}
          <circle cx="160" cy="45" r="18" fill="#f28c38" />
          <ellipse cx="160" cy="45" rx="28" ry="6" fill="none" stroke="#ffd6a5" strokeWidth="3" />
        </g>,
      );
    default:
      return <circle cx={W / 2} cy={H / 2 + 20} r={W / 2 - 8} fill="rgb(var(--soft))" />;
  }
}

/** Вещи за спиной: плащ, рюкзак */
function ExtraBehind({ code }: { code?: string }) {
  if (code === "cape") return <path d="M150 296 L372 296 L436 500 Q256 548 84 500 Z" fill="#d62839" />;
  if (code === "backpack") return <rect x="352" y="290" width="84" height="150" rx="26" fill="#f4a261" stroke="#c9733a" strokeWidth="7" />;
  return null;
}

type Paint = { fill: string; blend: CSSProperties["mixBlendMode"]; opacity?: number };

/** Цвет костюма: «color» меняет оттенок и сохраняет светотень, «multiply» — затемняет. */
const OUTFIT_PAINT: Record<string, Paint> = {
  tshirt: { fill: "#ef476f", blend: "color" },
  hoodie: { fill: "#2a9d8f", blend: "color" },
  school_uniform: { fill: "#264478", blend: "color" },
  tuxedo: { fill: "#23263a", blend: "multiply" },
  superhero: { fill: "#3a86ff", blend: "color" },
  astronaut: { fill: "#f4f6f8", blend: "normal", opacity: 0.82 },
  knight: { fill: "#c3cad2", blend: "normal", opacity: 0.8 },
};

/** Детали одежды внутри маски костюма (пояса, швы) */
function OutfitClipped({ code }: { code?: string }) {
  switch (code) {
    case "hoodie":
      return <rect x="188" y="398" width="130" height="44" rx="14" fill="#1f7a70" opacity="0.85" />;
    case "superhero":
      return <rect x="120" y="424" width="300" height="18" fill="#ffd166" />;
    case "astronaut":
      return <rect x="120" y="428" width="300" height="14" fill="#f28c38" />;
    case "knight":
      return <path d="M110 340 H420 M110 392 H420 M256 280 V480" stroke="#6c757d" strokeWidth="6" fill="none" />;
    default:
      return null;
  }
}

/** Детали одежды поверх (эмблемы, бабочка) */
function OutfitFront({ code }: { code?: string }) {
  switch (code) {
    case "tshirt":
      return <circle cx="300" cy="370" r="20" fill="#ffd166" stroke="#e09f3e" strokeWidth="4" />;
    case "hoodie":
      return <path d="M236 304 v48 M270 302 v48" stroke="#e9f5f3" strokeWidth="7" strokeLinecap="round" />;
    case "school_uniform":
      return <path d="M284 318 h36 v22 q-18 20 -36 0 Z" fill="#ffd166" stroke="#e09f3e" strokeWidth="3" />;
    case "tuxedo":
      return <path d="M204 292 L232 304 L260 292 L260 318 L232 306 L204 318 Z" fill="#d62839" stroke="#8d1624" strokeWidth="3" />;
    case "superhero":
      return (
        <path
          d="M256 332 l14 28 l31 5 l-23 21 l6 31 l-28 -15 l-28 15 l6 -31 l-23 -21 l31 -5 Z"
          fill="#d62839"
          stroke="#ffd166"
          strokeWidth="5"
          strokeLinejoin="round"
        />
      );
    case "astronaut":
      return (
        <g>
          <rect x="214" y="338" width="84" height="58" rx="10" fill="#adb5bd" stroke="#6c757d" strokeWidth="4" />
          <circle cx="238" cy="367" r="9" fill="#ef476f" />
          <circle cx="274" cy="367" r="9" fill="#06d6a0" />
        </g>
      );
    case "knight":
      return <path d="M222 316 h68 v44 q-34 34 -68 0 Z" fill="#d62839" stroke="#ffd166" strokeWidth="5" />;
    default:
      return null;
  }
}

function Glasses({ code }: { code?: string }) {
  if (code === "round_glasses")
    return (
      <g fill="rgb(255 255 255 / 0.18)" stroke={INK} strokeWidth="7">
        <circle cx="160" cy="164" r="32" />
        <circle cx="302" cy="152" r="32" />
        <path d="M192 158 Q232 138 270 148" fill="none" />
      </g>
    );
  if (code === "sunglasses")
    return (
      <g fill="#1f2230">
        <rect x="118" y="138" width="84" height="50" rx="20" />
        <rect x="260" y="126" width="84" height="50" rx="20" />
        <path d="M200 156 Q231 140 262 146" fill="none" stroke="#1f2230" strokeWidth="8" />
      </g>
    );
  if (code === "star_glasses") {
    const star = (cx: number, cy: number) =>
      `M${cx} ${cy - 36} l10 22 l25 3 l-19 17 l6 25 l-22 -13 l-22 13 l6 -25 l-19 -17 l25 -3 Z`;
    return (
      <g fill="#ff70a6" stroke="#c9184a" strokeWidth="5" strokeLinejoin="round">
        <path d={star(160, 164)} />
        <path d={star(302, 152)} />
        <path d="M192 160 Q232 140 270 150" fill="none" />
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
          <path d="M146 96 Q262 -48 382 86 Z" fill="#ef476f" />
          <path d="M262 90 H436 Q428 114 388 114 H262 Z" fill="#c9184a" />
          <circle cx="264" cy="24" r="10" fill="#c9184a" />
        </g>
      );
    case "headphones":
      return (
        <g>
          <path d="M122 188 Q112 -6 264 -6 Q416 -6 408 176" fill="none" stroke="#3a0ca3" strokeWidth="18" />
          <rect x="94" y="150" width="46" height="76" rx="18" fill="#7209b7" />
          <rect x="390" y="140" width="46" height="76" rx="18" fill="#7209b7" />
        </g>
      );
    case "wizard_hat":
      return (
        <g>
          <path d="M268 -60 L362 70 H174 Z" fill="#5a189a" />
          <ellipse cx="268" cy="70" rx="124" ry="20" fill="#3c096c" />
          <circle cx="254" cy="10" r="7" fill="#ffd166" />
          <circle cx="288" cy="40" r="6" fill="#ffd166" />
          <circle cx="266" cy="-24" r="5" fill="#ffd166" />
        </g>
      );
    case "grad_cap":
      return (
        <g>
          <rect x="200" y="36" width="136" height="38" fill="#1f2230" />
          <path d="M268 -8 L398 28 L268 64 L138 28 Z" fill="#2b2d42" />
          <path d="M372 28 V86" stroke="#ffd166" strokeWidth="7" />
          <circle cx="372" cy="92" r="10" fill="#ffd166" />
        </g>
      );
    case "crown":
      return (
        <g>
          <path d="M184 76 L184 4 L224 40 L268 -18 L312 40 L352 4 L352 76 Z" fill="#ffd166" stroke="#e09f3e" strokeWidth="7" strokeLinejoin="round" />
          <circle cx="268" cy="50" r="10" fill="#ef476f" />
        </g>
      );
    default:
      return null;
  }
}

/** Вещи спереди: шарф, медаль, лямка рюкзака */
function ExtraFront({ code }: { code?: string }) {
  if (code === "scarf")
    return (
      <g>
        <rect x="176" y="266" width="170" height="36" rx="18" fill="#e63946" />
        <rect x="292" y="284" width="32" height="84" rx="12" fill="#c1121f" />
      </g>
    );
  if (code === "medal")
    return (
      <g>
        <path d="M214 290 L256 362 L298 290" fill="none" stroke="#3a86ff" strokeWidth="14" />
        <circle cx="256" cy="382" r="28" fill="#ffd166" stroke="#e09f3e" strokeWidth="7" />
        <text x="256" y="394" textAnchor="middle" fontSize="32" fontWeight="900" fill="#9c6644">
          1
        </text>
      </g>
    );
  if (code === "backpack") return <path d="M370 298 V432" stroke="#c9733a" strokeWidth="12" strokeLinecap="round" />;
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
  const suit = `${id}-suit`;
  const s = SCALE[stage];
  const paint = equipped.outfit ? OUTFIT_PAINT[equipped.outfit] : undefined;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={size}
      height={Math.round((size * H) / W)}
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <clipPath id={frame}>
          <rect width={W} height={H} rx="72" />
        </clipPath>
        <mask id={suit} maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">
          <image href="/mascot-suit-mask.png" width="512" height="512" />
        </mask>
      </defs>
      <g clipPath={`url(#${frame})`}>
        <Background code={equipped.background} />
        <ellipse cx={W / 2} cy={FEET} rx={150 * s} ry="16" fill="rgb(0 0 0 / 0.16)" />
        {/* рост — масштаб от ног: вещи остаются на своих местах */}
        <g transform={`translate(${W / 2} ${FEET}) scale(${s}) translate(${-W / 2} ${-FEET})`}>
          {/* «живой» персонаж дышит (globals.css; выключается при «меньше движения») */}
          <g className="av-breathe" transform={`translate(0 ${TOP})`}>
            <ExtraBehind code={equipped.extra} />
            <g style={{ isolation: "isolate" }}>
              <image href="/mascot-512.webp" width="512" height="512" />
              {paint && (
                <g mask={`url(#${suit})`}>
                  <rect width="512" height="512" fill={paint.fill} opacity={paint.opacity} style={{ mixBlendMode: paint.blend }} />
                  <OutfitClipped code={equipped.outfit} />
                </g>
              )}
            </g>
            <OutfitFront code={equipped.outfit} />
            <Glasses code={equipped.glasses} />
            <Hat code={equipped.hat} />
            <ExtraFront code={equipped.extra} />
          </g>
        </g>
        {stage === "champion" && (
          <g fill="#ffd166">
            <path d="M52 150 l8 18 l18 8 l-18 8 l-8 18 l-8 -18 l-18 -8 l18 -8 Z" />
            <path d="M456 250 l6 15 l15 6 l-15 6 l-6 15 l-6 -15 l-15 -6 l15 -6 Z" />
          </g>
        )}
      </g>
    </svg>
  );
}
