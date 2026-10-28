import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Lang } from "../api";
import { lsGet, lsSet } from "../util";
import { en } from "./en";
import { hi } from "./hi";

export type Key = keyof typeof en;
export const dicts: Record<Lang, Record<Key, string>> = { en, hi };
type Vars = Record<string, string | number>;

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: Key, vars?: Vars) => string;
  /** Pick the current language from a bilingual {en, hi} field (rubric content). */
  pick: (b: { en: string; hi: string } | null | undefined) => string;
}

const LANG_KEY = "hunar.lang";

function initialLang(): Lang {
  const saved = lsGet(LANG_KEY);
  return saved === "hi" || saved === "en" ? saved : "en";
}

export function format(s: string, vars?: Vars): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    lsSet(LANG_KEY, l);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const value = useMemo<I18n>(
    () => ({
      lang,
      setLang,
      t: (key, vars) => format(dicts[lang][key] ?? en[key], vars),
      pick: (b) => (b ? b[lang] || b.en : ""),
    }),
    [lang, setLang],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}
