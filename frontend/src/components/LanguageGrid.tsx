import { useEffect } from "react";
import { localeAvailable, useI18n, type Lang } from "../i18n";
import { ensureFont, LANGUAGES } from "../i18n/languages";

/** All 23 languages, each name in its own script. Picking one switches the app at once. */
export function LanguageGrid({ onPick }: { onPick?: (l: Lang) => void }) {
  const { t, lang, setLang } = useI18n();
  useEffect(() => {
    // Only the few glyphs of these two names; the full font loads when the language is chosen.
    for (const l of LANGUAGES) if (l.font) ensureFont(l.code, l.endonym);
  }, []);
  return (
    <div className="lang-grid" role="radiogroup" aria-label={t("onb.chooseLang")}>
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          type="button"
          role="radio"
          aria-checked={lang === l.code}
          className={`lang-opt ${lang === l.code ? "on" : ""}`}
          onClick={() => {
            setLang(l.code);
            onPick?.(l.code);
          }}
        >
          <span className="lang-endonym" lang={l.htmlLang} dir={l.dir}>
            {l.endonym}
          </span>
          <span className="lang-english" lang="en">
            {l.english}
          </span>
          {!localeAvailable(l.code) && <span className="lang-note">{t("lang.englishForNow")}</span>}
        </button>
      ))}
    </div>
  );
}
