"use client";

/* «Мой носорог»: персонаж растёт с уровнем; очки меняются на коины, за коины —
   вещи. Нажатая вещь сразу примеряется на персонажа, покупка — отдельной кнопкой. */
import { useEffect, useState } from "react";
import { Avatar, type Equipped, type Stage } from "@/components/Avatar";
import { RequireStudent } from "@/components/RequireStudent";
import { Dots, IconButton, Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { publishMyAvatar } from "@/lib/myAvatar";

type Slot = "hat" | "outfit" | "glasses" | "extra" | "background";
type Item = { code: string; slot: Slot; price: number; min_level: number };
type AvatarState = {
  coins: number;
  points: number;
  free_points: number;
  points_per_coin: number;
  level: number;
  stage: Stage;
  next_stage_level: number | null;
  owned: string[];
  equipped: Equipped;
  catalog: Item[];
};

const SLOTS: Slot[] = ["outfit", "hat", "glasses", "extra", "background"];
const ICON: Record<string, string> = {
  cap: "🧢", headphones: "🎧", wizard_hat: "🧙", grad_cap: "🎓", crown: "👑",
  tshirt: "👕", hoodie: "🧥", school_uniform: "👔", tuxedo: "🤵", superhero: "🦸", astronaut: "🧑‍🚀", knight: "🛡️",
  round_glasses: "👓", sunglasses: "🕶️", star_glasses: "🤩",
  scarf: "🧣", backpack: "🎒", cape: "🦹", medal: "🏅",
  park: "🌳", sea: "🌊", classroom: "🏫", space: "🌌",
};

function Exchange({ state, onDone, onError }: { state: AvatarState; onDone: (s: AvatarState) => void; onError: (c: string | null) => void }) {
  const t = useT();
  const rate = state.points_per_coin;
  const max = Math.floor(state.free_points / rate);
  const [coins, setCoins] = useState(Math.min(10, max));
  const [busy, setBusy] = useState(false);

  useEffect(() => setCoins((c) => Math.min(Math.max(c, max > 0 ? 1 : 0), max)), [max]);

  if (max === 0) return <p className="text-center text-sm font-semibold text-muted">{t("avatar.exchange_none")}</p>;

  const step = (d: number) => setCoins((c) => Math.min(max, Math.max(1, c + d)));
  const submit = async () => {
    setBusy(true);
    onError(null);
    try {
      onDone(await api<AvatarState>("/v1/avatar/exchange", { method: "POST", json: { points: coins * rate } }));
    } catch (err) {
      onError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <button type="button" className="chip justify-center px-0 text-lg w-12" onClick={() => step(-10)} aria-label="-10">
          −
        </button>
        <output className="flex-1 text-center text-3xl font-black" aria-live="polite">
          {coins} 🪙
        </output>
        <button type="button" className="chip justify-center px-0 text-lg w-12" onClick={() => step(10)} aria-label="+10">
          +
        </button>
        <button type="button" className="chip" onClick={() => setCoins(max)}>
          {t("avatar.exchange_max")}
        </button>
      </div>
      <button type="button" className="btn btn-primary" disabled={busy || coins < 1} onClick={submit}>
        {busy ? <Dots /> : t("avatar.exchange_get", { coins, points: coins * rate })}
      </button>
    </div>
  );
}

function AvatarScreen() {
  const t = useT();
  const [state, setState] = useState<AvatarState | null>(null);
  const [slot, setSlot] = useState<Slot>("outfit");
  const [selected, setSelected] = useState<string | null>(null); // примеряем
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AvatarState>("/v1/avatar").then(setState).catch((e) => setError(errorCode(e)));
  }, []);

  // Новый образ сразу виден везде, где маскот (главная, профиль, уроки)
  useEffect(() => {
    if (state) publishMyAvatar(state);
  }, [state]);

  if (!state) return error ? <Page><Notice tone="error">{t(`errors.${error}`)}</Notice></Page> : <Splash />;

  const item = state.catalog.find((i) => i.code === selected) ?? null;
  const preview: Equipped = item ? { ...state.equipped, [item.slot]: item.code } : state.equipped;

  const act = async (path: "buy" | "equip", json: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      setState(await api<AvatarState>(`/v1/avatar/${path}`, { method: "POST", json }));
      setSelected(null);
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  let action: JSX.Element | null = null;
  if (item) {
    const owned = state.owned.includes(item.code);
    const worn = state.equipped[item.slot] === item.code;
    if (owned) {
      action = (
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => act("equip", { item: item.code, equipped: !worn })}>
          {busy ? <Dots /> : worn ? t("avatar.take_off") : t("avatar.wear")}
        </button>
      );
    } else if (state.level < item.min_level) {
      action = <p className="text-center font-bold text-muted">{t("avatar.locked", { level: item.min_level })}</p>;
    } else {
      const short = item.price - state.coins;
      action = (
        <button type="button" className="btn btn-primary" disabled={busy || short > 0} onClick={() => act("buy", { item: item.code })}>
          {busy ? <Dots /> : short > 0 ? t("avatar.need_coins", { n: short }) : t("avatar.buy", { price: item.price })}
        </button>
      );
    }
  }

  return (
    <Page className="gap-5">
      <header className="flex items-center gap-3">
        <IconButton href="/" label={t("profile.back")}>‹</IconButton>
        <h1 className="min-w-0 flex-1 text-2xl font-black leading-tight">🦏 {t("avatar.title")}</h1>
        <span className="rounded-full bg-soft px-3 py-1.5 text-lg font-black" title={t("avatar.coins")}>
          {state.coins} 🪙
        </span>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <section className="card flex flex-col items-center gap-2 anim-rise">
        <Avatar stage={state.stage} equipped={preview} size={220} label={t("avatar.title")} />
        <p className="text-xl font-black">
          {t(`avatar.stages.${state.stage}`)} · {t("avatar.level", { level: state.level })}
        </p>
        <p className="text-sm font-bold text-muted">
          {state.next_stage_level ? t("avatar.grows_at", { level: state.next_stage_level }) : t("avatar.max_stage")}
        </p>
        {item && (
          <div className="flex w-full flex-col gap-2 border-t-[length:var(--border-w)] border-line pt-3">
            <p className="text-center font-black">
              {ICON[item.code]} {t(`avatar.items.${item.code}`)}
            </p>
            {action}
          </div>
        )}
      </section>

      <section className="card flex flex-col gap-3 anim-rise" aria-labelledby="exchange-title">
        <div className="flex items-baseline justify-between gap-2">
          <h2 id="exchange-title" className="text-lg font-black">⭐ → 🪙 {t("avatar.exchange_title")}</h2>
          <span className="text-sm font-bold text-muted">{t("avatar.exchange_rate", { points: state.points_per_coin })}</span>
        </div>
        <p className="text-sm font-bold">
          {t("avatar.free_points")}: <span className="font-black">{state.free_points} ⭐</span>
        </p>
        <Exchange state={state} onDone={setState} onError={setError} />
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="shop-title">
        <h2 id="shop-title" className="label">🛍️ {t("avatar.shop_title")}</h2>
        <div className="grid grid-cols-5 gap-1.5" role="tablist">
          {SLOTS.map((s) => (
            <button
              key={s}
              type="button"
              role="tab"
              aria-selected={slot === s}
              aria-pressed={slot === s}
              className="chip min-w-0 justify-center px-0.5 text-[11px] sm:text-sm"
              onClick={() => setSlot(s)}
            >
              {t(`avatar.slots.${s}`)}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {state.catalog
            .filter((i) => i.slot === slot)
            .map((i) => {
              const owned = state.owned.includes(i.code);
              const worn = state.equipped[i.slot] === i.code;
              const locked = !owned && state.level < i.min_level;
              return (
                <button
                  key={i.code}
                  type="button"
                  aria-pressed={selected === i.code}
                  onClick={() => setSelected(selected === i.code ? null : i.code)}
                  className={`flex min-w-0 flex-col items-center gap-1 rounded-2xl border-[length:var(--border-w)] bg-surface p-2 text-center transition-colors ${
                    selected === i.code ? "border-primary" : "border-line"
                  } ${locked ? "opacity-60" : ""}`}
                >
                  <span className="text-3xl" aria-hidden="true">{ICON[i.code]}</span>
                  <span className="line-clamp-2 min-h-[2rem] w-full text-xs font-extrabold leading-tight">{t(`avatar.items.${i.code}`)}</span>
                  <span className="text-xs font-bold text-muted">
                    {worn ? `✅ ${t("avatar.worn")}` : owned ? t("avatar.owned") : locked ? t("avatar.locked", { level: i.min_level }) : `${i.price} 🪙`}
                  </span>
                </button>
              );
            })}
        </div>
      </section>
    </Page>
  );
}

export default function AvatarPage() {
  return (
    <RequireStudent>
      <AvatarScreen />
    </RequireStudent>
  );
}
