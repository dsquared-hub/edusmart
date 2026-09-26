"use client";

/* Сцена с 3D-носорогом для входа: носорог «выпрыгивает», за ним медленно вращается
   неоновый ореол, вокруг плавают значки предметов. Всё движение выключается
   при «меньше движения» (globals.css). */
import { Mascot3D } from "./Mascot3D";

const ORBIT = ["➗", "📐", "🧪", "🌍", "📖", "💡"];

export function RhinoHero({ size = 180, label }: { size?: number; label?: string }) {
  const box = Math.round(size * 1.7);
  return (
    <div className="relative grid place-items-center" style={{ width: box, height: box }}>
      <span className="hero-halo absolute inset-[8%] rounded-full" aria-hidden="true" />
      <span className="absolute inset-[18%] rounded-full bg-surface/70 blur-sm" aria-hidden="true" />
      <ul className="hero-orbit absolute inset-0" aria-hidden="true">
        {ORBIT.map((icon, i) => (
          <li
            key={icon}
            className="hero-bubble absolute grid h-11 w-11 place-items-center rounded-2xl bg-surface text-xl shadow-lg"
            style={{
              left: `${50 + 44 * Math.cos((i / ORBIT.length) * 2 * Math.PI)}%`,
              top: `${50 + 44 * Math.sin((i / ORBIT.length) * 2 * Math.PI)}%`,
              animationDelay: `${0.5 + i * 0.12}s, 0s`,
            }}
          >
            {icon}
          </li>
        ))}
      </ul>
      <span className="hero-rhino relative">
        <Mascot3D size={size} label={label} />
      </span>
    </div>
  );
}
