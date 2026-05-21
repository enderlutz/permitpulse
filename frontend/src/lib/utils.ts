import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const formatNum = (n: number | null | undefined, opts?: Intl.NumberFormatOptions) =>
  n == null ? "—" : new Intl.NumberFormat("en-US", opts).format(n);

export const formatPct = (n: number | null | undefined, digits = 1) =>
  n == null ? "—" : `${n >= 0 ? "↑" : "↓"}${Math.abs(n).toFixed(digits)}%`;

export const formatDate = (s: string | null | undefined) => {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

export const formatRelativeDate = (s: string | null | undefined) => {
  if (!s) return "—";
  const d = new Date(s);
  const diffMs = Date.now() - d.getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
};
