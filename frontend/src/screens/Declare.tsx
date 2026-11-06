import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createDeclaration } from "../actions";
import { errorText } from "../api";
import { ErrorText, Notice } from "../components/common";
import { VoiceInput } from "../components/VoiceInput";
import { useI18n } from "../i18n";
import { actorName, useSettings } from "../settings";

/** The rubric to assess against; appliance_technician is the ceiling-fan video pilot (DRAFT). */
const TRADE_CHOICES = ["electrician", "plumber", "carpenter", "appliance_technician"] as const;

function randomCode(): string {
  const n = new Uint16Array(1);
  crypto.getRandomValues(n);
  return `W-${String(n[0] % 10000).padStart(4, "0")}`;
}

/** Heuristic: two or more alphabetic words (Latin or Devanagari) look like a person's name. */
function looksLikeName(code: string): boolean {
  return /^[\p{L}\p{M}]+(\s+[\p{L}\p{M}]+)+$/u.test(code.trim());
}

export function Declare() {
  const { t } = useI18n();
  const settings = useSettings();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState<"hi" | "en">("hi");
  const [trade, setTrade] = useState<(typeof TRADE_CHOICES)[number]>("electrician");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  // A transcript is an AI draft: the facilitator must read it back to the worker before saving.
  const [usedVoice, setUsedVoice] = useState(false);
  const [readBack, setReadBack] = useState(false);

  const codeOk = code.trim().length >= 1 && code.trim().length <= 32;
  const textOk = text.trim().length >= 3;
  const nameWarning = looksLikeName(code);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!codeOk || !textOk || nameWarning || (usedVoice && !readBack)) return;
    setBusy(true);
    setError(null);
    try {
      const id = await createDeclaration({
        code: code.trim(),
        preferred_language: language,
        declaration_text: text.trim(),
        actor: actorName(settings),
        trade,
      });
      navigate(`/a/${id}/mapping`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <form className="stack" onSubmit={(e) => void submit(e)} noValidate>
      <h1>{t("declare.title")}</h1>
      <section className="card stack">
        <label className="field">
          <span className="label">{t("declare.codeLabel")}</span>
          <div className="row gap">
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={32}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              aria-invalid={touched && (!codeOk || nameWarning)}
              aria-describedby="code-hint"
              className="grow"
            />
            <button type="button" className="btn" onClick={() => setCode(randomCode())}>
              {t("declare.codeGenerate")}
            </button>
          </div>
          <span id="code-hint" className="hint">
            ⚠ {t("declare.codeHint")}
          </span>
        </label>
        {nameWarning && <Notice kind="warn" role="alert">{t("declare.codeLooksLikeName")}</Notice>}
        {touched && !codeOk && <Notice kind="error">{t("declare.codeRequired")}</Notice>}

        <fieldset className="field">
          <legend className="label">{t("declare.tradeLabel")}</legend>
          <div className="seg">
            {TRADE_CHOICES.map((tr) => (
              <label key={tr} className={`seg-opt ${trade === tr ? "on" : ""}`}>
                <input type="radio" name="trade" value={tr} checked={trade === tr} onChange={() => setTrade(tr)} />
                {t(`trade.${tr}`)}
              </label>
            ))}
          </div>
          {trade !== "electrician" && <span className="hint">{t("declare.tradeHint")}</span>}
        </fieldset>

        <fieldset className="field">
          <legend className="label">{t("declare.langLabel")}</legend>
          <div className="seg">
            {(["hi", "en"] as const).map((l) => (
              <label key={l} className={`seg-opt ${language === l ? "on" : ""}`}>
                <input type="radio" name="lang" value={l} checked={language === l} onChange={() => setLanguage(l)} />
                {t(l === "hi" ? "lang.hi" : "lang.en")}
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <section className="card stack">
        <label className="field">
          <span className="label">{t("declare.textLabel")}</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            aria-describedby="decl-hint"
            aria-invalid={touched && !textOk}
          />
          <span id="decl-hint" className="hint">
            {t("declare.textHint")}
          </span>
        </label>
        {touched && !textOk && <Notice kind="error">{t("declare.tooShort")}</Notice>}
        <VoiceInput
          language={language}
          onText={(spoken) => {
            setText((prev) => (prev.trim() ? `${prev.trim()}\n${spoken}` : spoken));
            setUsedVoice(true);
            setReadBack(false);
          }}
        />
        {usedVoice && (
          <label className="check">
            <input type="checkbox" checked={readBack} onChange={(e) => setReadBack(e.target.checked)} />
            <span>{t("voice.readBack")}</span>
          </label>
        )}
        {touched && usedVoice && !readBack && <Notice kind="error">{t("voice.readBackRequired")}</Notice>}
      </section>

      <ErrorText error={error} />
      <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
        {busy ? t("declare.saving") : t("declare.submit")}
      </button>
    </form>
  );
}
