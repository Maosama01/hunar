// The 23 app languages: English and the 22 languages of the Eighth Schedule (same list and codes as
// backend/hunar/accounts/routes.py LANGUAGES). Each name is written in its own script (endonym).

export type LangCode =
  | "en" | "as" | "bn" | "brx" | "doi" | "gu" | "hi" | "kn" | "ks" | "gom" | "mai" | "ml"
  | "mni" | "mr" | "ne" | "or" | "pa" | "sa" | "sat" | "sd" | "ta" | "te" | "ur";

export interface LangInfo {
  code: LangCode;
  /** The language's name in its own script. */
  endonym: string;
  /** English name (small print for facilitators). */
  english: string;
  /** Value for the HTML lang attribute (script subtag where the default script is ambiguous). */
  htmlLang: string;
  /** BCP-47 tags to look for in speech voices and to format dates, best first. */
  bcp47: string[];
  dir: "ltr" | "rtl";
  /** Web font loaded only when this language is chosen (system fonts rarely cover these scripts). */
  font?: { family: string; css: string };
}

const L = (
  code: LangCode,
  endonym: string,
  english: string,
  bcp47: string[],
  extra: Partial<Pick<LangInfo, "dir" | "font" | "htmlLang">> = {},
): LangInfo => ({ code, endonym, english, bcp47, htmlLang: extra.htmlLang ?? code, dir: extra.dir ?? "ltr", font: extra.font });

const gf = (family: string) => ({
  family,
  css: `https://fonts.googleapis.com/css2?family=${family.replace(/ /g, "+")}&display=swap`,
});

export const LANGUAGES: LangInfo[] = [
  L("en", "English", "English", ["en-IN", "en-GB", "en-US", "en"]),
  L("as", "অসমীয়া", "Assamese", ["as-IN", "as"]),
  L("bn", "বাংলা", "Bengali", ["bn-IN", "bn-BD", "bn"]),
  L("brx", "बड़ो", "Bodo", ["brx-IN", "brx"]),
  L("doi", "डोगरी", "Dogri", ["doi-IN", "doi"]),
  L("gu", "ગુજરાતી", "Gujarati", ["gu-IN", "gu"]),
  L("hi", "हिन्दी", "Hindi", ["hi-IN", "hi"]),
  L("kn", "ಕನ್ನಡ", "Kannada", ["kn-IN", "kn"]),
  L("ks", "کٲشُر", "Kashmiri", ["ks-IN", "ks-Arab-IN", "ks"], { dir: "rtl", htmlLang: "ks-Arab" }),
  L("gom", "कोंकणी", "Konkani", ["gom-IN", "kok-IN", "gom", "kok"]),
  L("mai", "मैथिली", "Maithili", ["mai-IN", "mai"]),
  L("ml", "മലയാളം", "Malayalam", ["ml-IN", "ml"]),
  L("mni", "ꯃꯩꯇꯩꯂꯣꯟ", "Manipuri (Meitei)", ["mni-Mtei-IN", "mni-IN", "mni"], {
    htmlLang: "mni-Mtei",
    font: gf("Noto Sans Meetei Mayek"),
  }),
  L("mr", "मराठी", "Marathi", ["mr-IN", "mr"]),
  L("ne", "नेपाली", "Nepali", ["ne-IN", "ne-NP", "ne"]),
  L("or", "ଓଡ଼ିଆ", "Odia", ["or-IN", "or"]),
  L("pa", "ਪੰਜਾਬੀ", "Punjabi", ["pa-IN", "pa-Guru-IN", "pa"]),
  L("sa", "संस्कृतम्", "Sanskrit", ["sa-IN", "sa"]),
  L("sat", "ᱥᱟᱱᱛᱟᱲᱤ", "Santali (Ol Chiki)", ["sat-Olck-IN", "sat-IN", "sat"], {
    htmlLang: "sat-Olck",
    font: gf("Noto Sans Ol Chiki"),
  }),
  L("sd", "سنڌي", "Sindhi", ["sd-IN", "sd-Arab-IN", "sd"], { dir: "rtl", htmlLang: "sd-Arab" }),
  L("ta", "தமிழ்", "Tamil", ["ta-IN", "ta"]),
  L("te", "తెలుగు", "Telugu", ["te-IN", "te"]),
  L("ur", "اردو", "Urdu", ["ur-IN", "ur-PK", "ur"], { dir: "rtl" }),
];

const BY_CODE = new Map(LANGUAGES.map((l) => [l.code, l]));

export function isLangCode(x: unknown): x is LangCode {
  return typeof x === "string" && BY_CODE.has(x as LangCode);
}

export function langInfo(code: string): LangInfo {
  return BY_CODE.get(code as LangCode) ?? BY_CODE.get("en")!;
}

export function endonym(code: string): string {
  return BY_CODE.get(code as LangCode)?.endonym ?? code;
}

/** Languages usually written in Devanagari: for API content that only exists in English and Hindi,
 * readers of these languages get the Hindi text; everyone else gets English. */
export const DEVANAGARI = new Set<string>(["hi", "mr", "ne", "sa", "mai", "doi", "brx", "gom"]);

/** Locale for Intl date formatting; falls back to en-IN when the runtime does not know the tag. */
export function intlLocale(code: string): string {
  const tags = langInfo(code).bcp47;
  for (const tag of tags) {
    try {
      if (Intl.DateTimeFormat.supportedLocalesOf([tag]).length) return tag;
    } catch {
      /* invalid tag on this runtime */
    }
  }
  return "en-IN";
}

/** Load the web font for a script once (Ol Chiki, Meetei Mayek). With `text`, only the glyphs needed
 * to draw that text are fetched (used for the endonyms in the language picker). */
export function ensureFont(code: string, text?: string): void {
  const info = BY_CODE.get(code as LangCode);
  if (!info?.font || typeof document === "undefined") return;
  const fullId = `font-${code}`;
  if (document.getElementById(fullId)) return; // the full font is already there
  const id = text ? `font-${code}-subset` : fullId;
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = text ? `${info.font.css}&text=${encodeURIComponent(text)}` : info.font.css;
  document.head.appendChild(link);
}
