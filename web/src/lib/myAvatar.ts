"use client";

// Аватар вошедшего ученика — один на всё приложение: после входа он заменяет
// общего носорога-маскота. Загружается один раз; страница /avatar сообщает об изменениях.
import { useEffect, useState } from "react";
import type { Equipped, Stage } from "@/components/Avatar";
import { api } from "@/lib/api";

export type MyAvatar = { stage: Stage; equipped: Equipped };

let owner: number | null = null; // id пользователя, чей аватар в кэше
let current: MyAvatar | null = null;
let inflight: Promise<void> | null = null;
const listeners = new Set<() => void>();

const notify = () => listeners.forEach((fn) => fn());

export function publishMyAvatar(state: MyAvatar): void {
  current = { stage: state.stage, equipped: state.equipped };
  notify();
}

function load(userId: number): void {
  if (owner === userId && (current || inflight)) return;
  owner = userId;
  current = null;
  inflight = api<MyAvatar>("/v1/avatar")
    .then((s) => {
      if (owner === userId) publishMyAvatar(s);
    })
    .catch(() => undefined) // нет доступа (нет согласия и т. п.) — останется носорог
    .finally(() => {
      inflight = null;
    });
}

/** Аватар ученика или null (гость, взрослый, ещё грузится) — тогда показываем носорога. */
export function useMyAvatar(userId: number | null | undefined, isStudent: boolean): MyAvatar | null {
  const [, rerender] = useState(0);
  useEffect(() => {
    const fn = () => rerender((n) => n + 1);
    listeners.add(fn);
    if (userId && isStudent) load(userId);
    return () => {
      listeners.delete(fn);
    };
  }, [userId, isStudent]);
  return userId && isStudent && owner === userId ? current : null;
}
