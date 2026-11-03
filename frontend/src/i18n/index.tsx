// UI strings. locales/en.json is the source of keys; hi.json must have every key (checked below at
// compile time). Other languages are optional files locales/<code>.json, loaded on demand; missing keys
// fall back to English. Optional "_meta": {provider, reviewed, generated} describes how a file was made.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";
import { getToken, updateAccount } from "../session";
import { lsGet, lsSet } from "../util";
import en from "./locales/en.json";
import hi from "./locales/hi.json";
import { DEVANAGARI, ensureFont, isLangCode, langInfo, type LangCode } from "./languages";

export type Key = Exclude<keyof typeof en, "_meta">;
export type Lang = LangCode;
type Vars = Record<string, string | number>;

export interface LocaleMeta {
  provider?: string;
  reviewed?: boolean;
  generated?: string;
}

type Dict = Partial<Record<Key, string>> & { _meta?: LocaleMeta };

// Dev server only: hot-swapping this module (or a locale file) would create a second React context;
// reload the page instead.
import.meta.hot?.accept(() => window.location.reload());

// Compile-time check: the Hindi file has every English key.
const hiDict: Record<Key, string> & { _meta?: LocaleMeta } = hi;
const enDict: Record<Key, string> = en;
const KEY_COUNT = Object.keys(en).filter((k) => k !== "_meta").length;

/** Optional language files, each loaded only when that language is chosen. */
const lazyLocales = import.meta.glob<{ default: Dict }>(["./locales/*.json", "!./locales/en.json", "!./locales/hi.json"]);

export function localeAvailable(code: string): boolean {
  return code === "en" || code === "hi" || `./locales/${code}.json` in lazyLocales;
}

export interface Coverage {
  /** A file exists for this language. */
  exists: boolean;
  /** Share of UI keys translated (0..1). */
  share: number;
  meta: LocaleMeta | null;
}

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: Key, vars?: Vars) => string;
  /** True when the current language file has its own text for this key. */
  has: (key: Key) => boolean;
  /** Language the text of `key` is shown in (English when it fell back), for lang attributes and read-aloud. */
  langOf: (key: Key) => string;
  /** Text the API sends in English, shown translated when the UI has a string for it. The English UI
   * always shows the API's own text, so it never drifts from the server. */
  apiText: (key: Key, apiValue: string | null | undefined, vars?: Vars) => string;
  /** Pick from bilingual API content ({en, hi, [lang]?}). */
  pick: (b: BiText | null | undefined) => string;
  /** Same as pick, also returning the language of the text (for lang attributes and read-aloud). */
  pickL: (b: BiText | null | undefined) => [string, string];
  coverage: Coverage;
  loading: boolean;
}

/** Bilingual API content; some fields may also carry other languages (e.g. {en, hi, ta}). */
export type BiText = { en: string; hi: string };

const LANG_KEY = "hunar.lang";

export function hasChosenLanguage(): boolean {
  return isLangCode(lsGet(LANG_KEY));
}

function initialLang(): Lang {
  const saved = lsGet(LANG_KEY);
  if (isLangCode(saved)) return saved;
  const nav = typeof navigator !== "undefined" ? navigator.language.split("-")[0] : "en";
  return isLangCode(nav) ? nav : "en";
}

export function format(s: string, vars?: Vars): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

function coverageOf(dict: Dict | null): Coverage {
  if (!dict) return { exists: false, share: 0, meta: null };
  let n = 0;
  for (const k of Object.keys(en) as Key[]) if (typeof dict[k] === "string" && dict[k]!.trim()) n++;
  return { exists: true, share: n / KEY_COUNT, meta: dict._meta ?? null };
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const [dict, setDict] = useState<Dict | null>(() => (lang === "en" ? enDict : lang === "hi" ? hiDict : null));
  const [loading, setLoading] = useState(false);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    lsSet(LANG_KEY, l);
    // Logged in: remember the choice on the account too, so it follows the person to another device.
    if (getToken()) void api.updateMe({ language: l }).then(updateAccount, () => undefined);
  }, []);

  useEffect(() => {
    let alive = true;
    const info = langInfo(lang);
    document.documentElement.lang = info.htmlLang;
    document.documentElement.dir = info.dir;
    ensureFont(lang);
    if (lang === "en") setDict(enDict);
    else if (lang === "hi") setDict(hiDict);
    else {
      const loader = lazyLocales[`./locales/${lang}.json`];
      if (!loader) setDict(null);
      else {
        setLoading(true);
        loader()
          .then((m) => alive && setDict(m.default))
          .catch(() => alive && setDict(null))
          .finally(() => alive && setLoading(false));
      }
    }
    return () => {
      alive = false;
    };
  }, [lang]);

  const value = useMemo<I18n>(() => {
    const own = (key: Key): string | undefined => {
      const v = dict?.[key];
      return typeof v === "string" && v.trim() ? v : undefined;
    };
    const t = (key: Key, vars?: Vars) => format(own(key) ?? enDict[key] ?? key, vars);
    const has = (key: Key) => lang === "en" || own(key) !== undefined;
    const pickL = (b: BiText | null | undefined): [string, string] => {
      if (!b) return ["", lang];
      const mine = (b as unknown as Record<string, unknown>)[lang];
      if (typeof mine === "string" && mine.trim()) return [mine, lang];
      if (DEVANAGARI.has(lang) && b.hi) return [b.hi, "hi"];
      return b.en ? [b.en, "en"] : [b.hi, "hi"];
    };
    return {
      lang,
      setLang,
      t,
      has,
      langOf: (key) => (has(key) ? lang : "en"),
      apiText: (key, apiValue, vars) => (apiValue && (lang === "en" || !has(key)) ? apiValue : t(key, vars)),
      pick: (b) => pickL(b)[0],
      pickL,
      coverage: coverageOf(dict),
      loading,
    };
  }, [lang, setLang, dict, loading]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}

/** English string for a key, outside React (e.g. the principle line in two languages). */
export function enText(key: Key): string {
  return enDict[key];
}

/** Whether a string is a UI key (for keys built at run time, e.g. per consent purpose). */
export function isKey(k: string): k is Key {
  return k !== "_meta" && Object.prototype.hasOwnProperty.call(enDict, k);
}
