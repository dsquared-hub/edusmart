// Носорог — маскот. Картинка с прозрачным фоном (public/mascot-*.webp),
// настроение показываем поверх неё: «думает» — пузырьки мыслей, «радуется» — искорки.
type Mood = "happy" | "thinking" | "cheer";

export function Mascot({ mood = "happy", size = 96, className = "" }: { mood?: Mood; size?: number; className?: string }) {
  return (
    <span className={`mascot relative inline-block shrink-0 ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element -- статичная картинка, оптимизирована заранее */}
      <img
        src={size > 128 ? "/mascot-512.webp" : "/mascot-256.webp"}
        srcSet="/mascot-256.webp 256w, /mascot-512.webp 512w"
        sizes={`${size}px`}
        width={size}
        height={size}
        alt=""
        draggable={false}
        decoding="async"
        className="h-full w-full select-none object-contain"
      />
      {mood === "thinking" && (
        <svg viewBox="0 0 40 40" className="absolute -right-[12%] -top-[6%] h-[38%] w-[38%]" style={{ overflow: "visible" }}>
          <g fill="rgb(var(--surface))" stroke="rgb(var(--ink) / 0.35)" strokeWidth="1.5">
            <circle cx="6" cy="34" r="3" />
            <circle cx="14" cy="24" r="5" />
            <ellipse cx="28" cy="10" rx="11" ry="9" />
          </g>
          <text x="28" y="14" textAnchor="middle" fontSize="11" fontWeight="900" fill="rgb(var(--primary))">?</text>
        </svg>
      )}
      {mood === "cheer" && (
        <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" style={{ overflow: "visible" }}>
          <g fill="rgb(var(--accent))" stroke="rgb(var(--ink) / 0.25)" strokeWidth="1">
            <path d="M8 22 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" />
            <path d="M90 10 l2.5 6 6 2.5 -6 2.5 -2.5 6 -2.5 -6 -6 -2.5 6 -2.5z" />
            <path d="M94 58 l2 4.5 4.5 2 -4.5 2 -2 4.5 -2 -4.5 -4.5 -2 4.5 -2z" />
          </g>
        </svg>
      )}
    </span>
  );
}
