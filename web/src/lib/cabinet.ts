import type { Me } from "./types";

/** Главная страница роли: ученик — уроки, родитель — кабинет родителя, учитель — кабинет учителя. */
export function homePath(role: Me["role"] | undefined): string {
  if (role === "parent") return "/parent";
  if (role === "teacher") return "/teacher";
  return "/";
}
