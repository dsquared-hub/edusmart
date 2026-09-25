/* Куби — блочный 3D-персонаж EDU ProgressUZ (в духе «кубических» игровых аватаров,
   но собственный). Каждая часть тела — «кубик» из трёх граней: фронт, верх (светлее)
   и бок (темнее), так аватар выглядит объёмным без WebGL.
   7 этапов образа (stage 0–6) и настроения: idle, happy, support, thinking.
   Маскот никогда не грустит и не стыдит — только радуется или поддерживает. */
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { SKINS, useReducedMotion, type Mood } from "@/lib/store";

type Outfit = {
  torso: string;
  sleeve: "short" | "long";
  sleeveColor: string;
  legs: string;
  shorts: boolean;
  shoes: string;
  shirt?: string; // виден в вырезе жилета/пиджака
  collar?: boolean;
  lapels?: boolean;
  vNeck?: boolean;
  belt?: boolean;
  tie?: string;
  cuffs?: boolean;
  pocket?: string;
  watch?: boolean;
  medal?: boolean;
  aura?: boolean;
  stripes?: boolean;
};

const WHITE = "#F6F2EA";
export const OUTFITS: Outfit[] = [
  // 1. Новичок — футболка и шорты
  { torso: "#3FA7A0", sleeve: "short", sleeveColor: "#3FA7A0", legs: "#3B4A6B", shorts: true, shoes: "#EDEAE4" },
  // 2. Ученик — белая рубашка
  { torso: WHITE, sleeve: "long", sleeveColor: WHITE, legs: "#3B4A6B", shorts: true, shoes: "#EDEAE4", collar: true },
  // 3. Отличник — рубашка, брюки, ремень
  { torso: WHITE, sleeve: "long", sleeveColor: WHITE, legs: "#4A4F63", shorts: false, shoes: "#5B3A26", collar: true, belt: true },
  // 4. Знаток — жилет поверх рубашки
  { torso: "#8C6A4F", sleeve: "long", sleeveColor: WHITE, legs: "#4A4F63", shorts: false, shoes: "#5B3A26", shirt: WHITE, vNeck: true, belt: true },
  // 5. Эксперт — пиджак
  { torso: "#2F3B55", sleeve: "long", sleeveColor: "#2F3B55", legs: "#4A4F63", shorts: false, shoes: "#3E2A1E", shirt: WHITE, lapels: true, cuffs: true, pocket: "#E8B64C" },
  // 6. Мастер — полный костюм с галстуком
  { torso: "#33363F", sleeve: "long", sleeveColor: "#33363F", legs: "#33363F", shorts: false, shoes: "#1F1A17", shirt: WHITE, lapels: true, cuffs: true, tie: "#2F7FD6" },
  // 7. Легенда — премиальный костюм, часы, медаль, аура
  { torso: "#4A2A26", sleeve: "long", sleeveColor: "#4A2A26", legs: "#4A2A26", shorts: false, shoes: "#1F1A17", shirt: WHITE, lapels: true, cuffs: true, tie: "#E8B64C", watch: true, medal: true, aura: true, stripes: true, pocket: "#E8B64C" },
];

/** Осветлить (amt > 0) или затемнить (amt < 0) hex-цвет. */
function shade(hex: string, amt: number): string {
  const n = parseInt(hex.slice(1), 16);
  const mix = (c: number) => Math.round(amt > 0 ? c + (255 - c) * amt : c * (1 + amt));
  const r = mix(n >> 16), g = mix((n >> 8) & 255), b = mix(n & 255);
  return `rgb(${r} ${g} ${b})`;
}

const DEPTH = 9;

/** «Кубик»: фронт + верхняя грань + правая боковая грань. */
function Box({ x, y, w, h, c, top = true, children }: {
  x: number; y: number; w: number; h: number; c: string; top?: boolean; children?: ReactNode;
}) {
  const dx = DEPTH, dy = -DEPTH * 0.65;
  return (
    <g>
      {top && <path d={`M${x} ${y}L${x + dx} ${y + dy}H${x + w + dx}L${x + w} ${y}Z`} fill={shade(c, 0.28)} />}
      <path d={`M${x + w} ${y}L${x + w + dx} ${y + dy}V${y + h + dy}L${x + w} ${y + h}Z`} fill={shade(c, -0.25)} />
      <rect x={x} y={y} width={w} height={h} rx={2.5} fill={c} />
      {/* мягкий блик по фронту — «пластик» */}
      <rect x={x + 2} y={y + 2} width={w * 0.4} height={h - 4} rx={2} fill="#fff" opacity={0.1} />
      {children}
    </g>
  );
}

function Arm({ side, o, skin, angle }: { side: "l" | "r"; o: Outfit; skin: string; angle: number }) {
  const x = side === "l" ? 33 : 104;
  const sleeveH = o.sleeve === "short" ? 16 : 38;
  const px = x + 7.5, py = 80; // плечо — точка вращения
  return (
    <g transform={`rotate(${angle} ${px} ${py})`} style={{ transition: "transform .35s cubic-bezier(.3,1.4,.5,1)" }}>
      <Box x={x} y={78} w={15} h={46} c={skin} />
      <Box x={x} y={78} w={15} h={sleeveH} c={o.sleeveColor} />
      {o.cuffs && <rect x={x} y={78 + sleeveH - 4} width={15} height={4} fill={WHITE} />}
      {o.watch && side === "l" && (
        <g>
          <rect x={x - 0.5} y={78 + sleeveH} width={16} height={5} rx={1.5} fill="#C99A2E" />
          <circle cx={x + 7.5} cy={78 + sleeveH + 2.5} r={3.2} fill="#FFF3C4" stroke="#C99A2E" strokeWidth={1.2} />
        </g>
      )}
    </g>
  );
}

function Face({ mood }: { mood: Mood }) {
  const ink = "#2B1D14";
  if (mood === "happy") {
    return (
      <g>
        <path d="M60 44q5-6 10 0M82 44q5-6 10 0" stroke={ink} strokeWidth={3.2} fill="none" strokeLinecap="round" />
        <path d="M64 53h24q-1 12-12 12t-12-12z" fill={ink} />
        <path d="M69 60q7 5 14 0" fill="#E0707A" />
        <ellipse cx={57} cy={55} rx={5} ry={3} fill="#F29A9A" opacity={0.7} />
        <ellipse cx={95} cy={55} rx={5} ry={3} fill="#F29A9A" opacity={0.7} />
      </g>
    );
  }
  const look = mood === "thinking" ? { x: -2, y: -3 } : { x: 0, y: 0 };
  return (
    <g>
      <rect x={61 + look.x} y={36 + look.y} width={8} height={11} rx={2.5} fill={ink} />
      <rect x={83 + look.x} y={36 + look.y} width={8} height={11} rx={2.5} fill={ink} />
      <rect x={63 + look.x} y={38 + look.y} width={3} height={3.5} rx={1} fill="#fff" />
      <rect x={85 + look.x} y={38 + look.y} width={3} height={3.5} rx={1} fill="#fff" />
      {mood === "thinking" ? (
        <path d="M70 57h11" stroke={ink} strokeWidth={3} strokeLinecap="round" />
      ) : (
        <path d="M66 54q10 9 20 0" stroke={ink} strokeWidth={3.2} fill="none" strokeLinecap="round" />
      )}
      {mood !== "thinking" && (
        <>
          <ellipse cx={57} cy={55} rx={5} ry={3} fill="#F29A9A" opacity={mood === "support" ? 0.8 : 0.5} />
          <ellipse cx={95} cy={55} rx={5} ry={3} fill="#F29A9A" opacity={mood === "support" ? 0.8 : 0.5} />
        </>
      )}
    </g>
  );
}

export function Kubi({
  stage = 0,
  skin = 0,
  mood = "idle",
  size = 160,
  silhouette = false,
  className = "",
  label,
}: {
  stage?: number;
  skin?: number;
  mood?: Mood;
  size?: number;
  silhouette?: boolean;
  className?: string;
  label?: string;
}) {
  const reduced = useReducedMotion();
  const o = OUTFITS[Math.max(0, Math.min(6, stage))];
  const skinColor = SKINS[skin % SKINS.length];
  const arms = {
    idle: { l: 4, r: -4 },
    happy: { l: 150, r: -150 },
    support: { l: 4, r: -115 },
    thinking: { l: 4, r: -140 },
  }[mood];

  const body = (
    <g>
      {/* ноги */}
      {[53, 76].map((x) => (
        <g key={x}>
          <Box x={x} y={124} w={23} h={44} c={o.shorts ? skinColor : o.legs} top={false} />
          {o.shorts && <Box x={x} y={124} w={23} h={18} c={o.legs} top={false} />}
          {o.stripes && <path d={`M${x + 11.5} 126V166`} stroke="#E8B64C" strokeOpacity={0.35} strokeWidth={1} />}
          <Box x={x - 1} y={164} w={25} h={8} c={o.shoes} />
        </g>
      ))}
      <Arm side="l" o={o} skin={skinColor} angle={arms.l} />
      {/* торс */}
      <Box x={51} y={76} w={50} h={50} c={o.torso}>
        {o.stripes && [60, 70, 82, 92].map((x) => <path key={x} d={`M${x} 78V124`} stroke="#E8B64C" strokeOpacity={0.28} strokeWidth={1} />)}
        {(o.vNeck || o.lapels) && <path d="M66 77L76 104L86 77Z" fill={o.shirt} />}
        {o.lapels && (
          <g fill={shade(o.torso, -0.2)}>
            <path d="M62 77L76 108L70 110L58 80Z" />
            <path d="M90 77L76 108L82 110L94 80Z" />
          </g>
        )}
        {o.collar && (
          <g fill={shade(WHITE, -0.08)}>
            <path d="M64 76L76 84L70 90Z" />
            <path d="M88 76L76 84L82 90Z" />
          </g>
        )}
        {o.tie && <path d="M73 80h6l-1 4 3 18-5 5-5-5 3-18z" fill={o.tie} />}
        {o.collar && !o.tie && [90, 100, 110].map((y) => <circle key={y} cx={76} cy={y} r={1.4} fill="#C8BFAF" />)}
        {o.vNeck && [96, 106, 116].map((y) => <circle key={y} cx={76} cy={y} r={1.6} fill={shade(o.torso, -0.35)} />)}
        {o.pocket && <path d="M88 96h8v3l-8 1z" fill={o.pocket} />}
        {o.belt && (
          <g>
            <rect x={51} y={119} width={50} height={6} fill="#3E2A1E" />
            <rect x={72} y={118.5} width={9} height={7} rx={1.5} fill="#E8B64C" />
          </g>
        )}
        {o.medal && (
          <g>
            <path d="M60 80l4 12h4l-4-12z" fill="#2F7FD6" />
            <circle cx={64} cy={98} r={6} fill="#E8B64C" stroke="#B8862A" strokeWidth={1.5} />
            <path d="M64 94.5l1.1 2.3 2.5.3-1.8 1.7.5 2.5-2.3-1.2-2.3 1.2.5-2.5-1.8-1.7 2.5-.3z" fill="#FFF3C4" />
          </g>
        )}
      </Box>
      <Arm side="r" o={o} skin={skinColor} angle={arms.r} />
      {/* голова */}
      <Box x={46} y={18} w={60} h={54} c={skinColor}>
        {!silhouette && <Face mood={mood} />}
      </Box>
    </g>
  );

  const bob = reduced
    ? {}
    : mood === "happy"
      ? { animate: { y: [0, -12, 0, -6, 0] }, transition: { duration: 0.9, repeat: 2 } }
      : mood === "support"
        ? { animate: { rotate: [0, -3, 3, 0] }, transition: { duration: 1.6, repeat: Infinity } }
        : { animate: { y: [0, -3, 0] }, transition: { duration: 3.2, repeat: Infinity, ease: "easeInOut" as const } };

  return (
    <svg
      viewBox="0 0 160 190"
      width={size}
      height={(size * 190) / 160}
      className={className}
      role="img"
      aria-label={label ?? "Kubi"}
      style={{ overflow: "visible" }}
    >
      <defs>
        <radialGradient id="kubi-aura">
          <stop offset="0" stopColor="#FFE39A" stopOpacity={0.85} />
          <stop offset="1" stopColor="#E8B64C" stopOpacity={0} />
        </radialGradient>
      </defs>
      {/* тень на полу */}
      <ellipse cx={80} cy={176} rx={40} ry={6} fill="#3E2A1E" opacity={0.14} />
      {o.aura && !silhouette && (
        <g>
          <circle cx={80} cy={96} r={82} fill="url(#kubi-aura)" />
          {[
            [24, 40],
            [140, 56],
            [18, 128],
            [146, 132],
          ].map(([x, y], i) => (
            <motion.path
              key={i}
              d={`M${x} ${y - 6}l2 4 4 2-4 2-2 4-2-4-4-2 4-2z`}
              fill="#FFE08A"
              animate={reduced ? undefined : { opacity: [0.2, 1, 0.2], scale: [0.8, 1.15, 0.8] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.4 }}
              style={{ transformOrigin: `${x}px ${y}px` }}
            />
          ))}
        </g>
      )}
      <motion.g {...bob} style={{ transformOrigin: "80px 170px" }}>
        {silhouette ? (
          <g style={{ filter: "grayscale(1) brightness(0.55)" }} opacity={0.35}>
            {body}
          </g>
        ) : (
          body
        )}
      </motion.g>
      {mood === "thinking" && !silhouette && (
        <g>
          {/* var() в SVG работает только через style, не через атрибуты */}
          <circle cx={122} cy={20} r={3} style={{ fill: "rgb(var(--c-surface))", stroke: "rgb(var(--c-line))" }} />
          <circle cx={131} cy={9} r={5} style={{ fill: "rgb(var(--c-surface))", stroke: "rgb(var(--c-line))" }} />
          <text x={131} y={12.5} textAnchor="middle" fontSize={8} fontWeight={900} style={{ fill: "rgb(var(--c-coffee))" }}>
            ?
          </text>
        </g>
      )}
      {mood === "support" && !silhouette && (
        <path d="M124 60c-3-4-9-1-6 4l6 6 6-6c3-5-3-8-6-4z" fill="#E0707A" />
      )}
    </svg>
  );
}
