// Small helpers shared across the app.

/** RFC 4122 v4 UUID. crypto.randomUUID only exists in secure contexts (https or localhost), but a
 * facilitator may open the dev server over plain http on the LAN, so fall back to getRandomValues. */
export function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* not a secure context */
    }
  }
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

/** The API returns some timestamps without a zone (SQLite drops it); they are UTC. */
export function parseTs(s: string | null | undefined): Date | null {
  if (!s) return null;
  const hasZone = /([zZ]|[+-]\d\d:?\d\d)$/.test(s);
  const d = new Date(hasZone ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtTime(s: string | null | undefined, lang: string): string {
  const d = parseTs(s);
  if (!d) return "";
  try {
    return d.toLocaleString(lang === "hi" ? "hi-IN" : "en-IN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return d.toISOString();
  }
}

export function pct(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  return `${(x * 100).toFixed(digits)}%`;
}

export function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/** Read and write localStorage defensively: it can throw in private windows or when blocked. */
export function lsGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function lsSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the choice just is not remembered */
  }
}
