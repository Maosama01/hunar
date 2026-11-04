import { useState } from "react";
import { confirmPack } from "../actions";
import { errorText } from "../api";
import { usePacks, type AssessmentView } from "../data";
import { useI18n } from "../i18n";
import { actorName, useSettings } from "../settings";
import { Notice, PendingBadge } from "./common";

/** Step 1 of scoring: the assessor confirms the qualification pack. For electricians the top M1
 * suggestion is the default and any other choice (or a choice before the mapping exists) needs a
 * reason. Other trades have one qualification file, which is the default. */
export function PackConfirm({ view }: { view: AssessmentView }) {
  const { t } = useI18n();
  const settings = useSettings();
  const packs = usePacks();
  const electrician = view.trade === "electrician";
  const ranking = electrician ? (view.mapping?.ranking ?? []) : [];
  const tradePacks = (packs ?? []).filter((p) => (p.trade ?? "electrician") === view.trade);
  const top = electrician ? (ranking[0]?.nqr_id ?? null) : (tradePacks[0]?.nqr_id ?? null);
  const [editing, setEditing] = useState(false);
  const [choice, setChoice] = useState<number | null>(view.confirmed_nqr_id ?? top);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const titleOf = (id: number | null) =>
    ranking.find((r) => r.nqr_id === id)?.title ?? packs?.find((p) => p.nqr_id === id)?.title ?? String(id);

  if (view.confirmed_nqr_id !== null && !editing) {
    return (
      <section className="card">
        <h3>{t("score.packStep")}</h3>
        <div className="row wrap gap-s between">
          <p className="row wrap gap-s">
            ✔ <strong>{t("score.confirmedAs", { title: titleOf(view.confirmed_nqr_id) })}</strong>
            {view.confirmPending && <PendingBadge />}
          </p>
          {!view.signedOff && (
            <button type="button" className="btn btn-small" onClick={() => { setChoice(view.confirmed_nqr_id); setEditing(true); }}>
              {t("score.change")}
            </button>
          )}
        </div>
      </section>
    );
  }

  const sel = choice ?? top; // the mapping may arrive after the first render
  const needsReason = top === null ? electrician && !!view.declaration_text : sel !== top;
  const others = electrician ? tradePacks.filter((p) => !ranking.some((r) => r.nqr_id === p.nqr_id)) : [];
  const canSubmit = sel !== null && (!needsReason || reason.trim().length > 0) && !view.signedOff;

  const submit = async () => {
    if (!canSubmit || sel === null) return;
    setError(null);
    try {
      await confirmPack(view.id, sel, needsReason ? reason.trim() : null, actorName(settings));
      setEditing(false);
      setReason("");
    } catch (e) {
      setError(errorText(e));
    }
  };

  const option = (id: number, label: string, sub?: string) => (
    <label key={id} className={`radio-card ${sel === id ? "on" : ""}`}>
      <input type="radio" name="pack" checked={sel === id} onChange={() => setChoice(id)} />
      <span>
        <strong>{label}</strong>
        {sub && <span className="small muted block">{sub}</span>}
      </span>
    </label>
  );

  return (
    <section className="card stack-s">
      <h3>{t("score.packStep")}</h3>
      <p className="hint">{t(electrician ? "score.packHint" : "score.packHintTrade")}</p>
      <fieldset className="stack-s">
        <legend className="sr-only">{t("score.packStep")}</legend>
        {ranking.slice(0, 3).map((r, i) =>
          option(
            r.nqr_id,
            r.title,
            `${i === 0 ? `${t("score.topSuggestion")} · ` : ""}${t("score.suggestionRank", { n: r.rank, score: r.score.toFixed(2) })}`,
          ),
        )}
        {!electrician && tradePacks.map((p) => option(p.nqr_id, p.title, t("score.tradePack")))}
        {others.length > 0 && <p className="small muted">{t("score.otherPacks")}</p>}
        {others.map((p) => option(p.nqr_id, p.title, p.nsqf_level !== null ? t("mapping.nsqf", { level: p.nsqf_level }) : undefined))}
      </fieldset>
      {needsReason && (
        <label className="field">
          <span className="label">{t("score.reason")}</span>
          <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} aria-describedby="pack-reason-hint" />
          <span id="pack-reason-hint" className="hint">
            {top === null ? t("score.reasonNoMapping") : t("score.reasonRequired")}
          </span>
        </label>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      <div className="row gap">
        <button type="button" className="btn btn-primary" disabled={!canSubmit} onClick={() => void submit()}>
          {t("score.confirm")}
        </button>
        {editing && (
          <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>
            {t("common.cancel")}
          </button>
        )}
      </div>
    </section>
  );
}
