// Ask for a practical assessment. An assessor meets the worker, watches the practical tasks and
// decides; the quiz is only shown to the assessor as context.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type AssessmentRequest } from "../../api";
import { Loading, Notice } from "../../components/common";
import { Icon } from "../../components/Icon";
import { VoiceInput } from "../../components/VoiceInput";
import { ErrorBox, SpeakButton, useLoad } from "../../components/ui";
import { useI18n, type Key } from "../../i18n";
import { useSession } from "../../session";
import { useTrades } from "../../trades";
import { fmtDate, todayIso } from "../../util";

const STATUS_KEY: Record<AssessmentRequest["status"], Key> = {
  open: "assess.status.open",
  started: "assess.status.started",
  cancelled: "assess.status.cancelled",
};

export function AssessRequestScreen() {
  const { t, lang, langOf, pick } = useI18n();
  const { account } = useSession();
  const { trades } = useTrades();
  const reqs = useLoad(() => api.assessmentRequests(), []);
  const prof = useLoad(() => api.myProfile(), []);
  const [text, setText] = useState("");
  const [date, setDate] = useState("");
  const [usedVoice, setUsedVoice] = useState(false);
  const [readBack, setReadBack] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [touched, setTouched] = useState(false);

  const consentOk = !!account?.consents.assessment;
  const open = reqs.data?.find((r) => r.status === "open");
  // Only trades with practical tasks can be assessed (electricians so far); the server refuses others.
  const myTrade = prof.data ? trades?.[prof.data.trade] : undefined;
  const noPractical = myTrade?.practical_assessment === false;
  const textOk = text.trim().length >= 10;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!textOk || (usedVoice && !readBack)) return;
    setBusy(true);
    setError(null);
    try {
      await api.requestAssessment({ declaration_text: text.trim(), preferred_date: date || null });
      setText("");
      setDate("");
      setUsedVoice(false);
      await reqs.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const explain = t("assess.explain");
  return (
    <div className="stack">
      <h1>{t("assess.title")}</h1>
      <section className="card stack-s">
        <p>{explain}</p>
        <p className="small muted">{t("assess.quizContext")}</p>
        <SpeakButton text={explain} lang={langOf("assess.explain")} />
      </section>

      <ErrorBox error={reqs.error} />
      {reqs.loading && !reqs.data && <Loading />}

      {reqs.data && reqs.data.length > 0 && (
        <section className="card stack-s">
          <h2>{t("assess.myRequests")}</h2>
          <ul className="list">
            {reqs.data.map((r) => (
              <li key={r.id} className="list-item">
                <Icon name={r.status === "started" ? "check" : r.status === "open" ? "clock" : "inbox"} />
                <div className="list-main">
                  <strong>{t(STATUS_KEY[r.status])}</strong>
                  <div className="small muted">
                    {t("assess.sentOn", { date: fmtDate(r.created_at, lang) })}
                    {r.preferred_date ? ` · ${t("assess.preferred", { date: fmtDate(r.preferred_date, lang) })}` : ""}
                  </div>
                  {r.status === "open" && <div className="small">{t("assess.openHelp")}</div>}
                  {r.status === "open" && (
                    <button
                      type="button"
                      className="btn btn-small"
                      onClick={() => void api.cancelRequest(r.id).then(() => reqs.reload(), () => reqs.reload())}
                    >
                      {t("assess.cancel")}
                    </button>
                  )}
                  {r.status === "started" && <div className="small">{t("assess.startedHelp")}</div>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!consentOk ? (
        <Notice kind="warn">
          {t("assess.needConsent")} <Link to="/w/privacy">{t("nav.privacy")}</Link>
        </Notice>
      ) : prof.data === null ? (
        <Notice kind="warn">
          {t("assess.needProfile")} <Link to="/w/profile">{t("nav.myProfile")}</Link>
        </Notice>
      ) : noPractical ? (
        <Notice kind="info">{t("assess.notForTrade", { trade: pick(myTrade!.name) })}</Notice>
      ) : open ? (
        <Notice kind="info">{t("assess.alreadyOpen")}</Notice>
      ) : (
        reqs.data && (
          <form className="card stack" onSubmit={(e) => void submit(e)} noValidate>
            <h2>{t("assess.new")}</h2>
            <label className="field">
              <span className="label">{t("assess.declaration")}</span>
              <textarea rows={6} value={text} maxLength={3000} onChange={(e) => setText(e.target.value)} aria-describedby="decl-hint" aria-invalid={touched && !textOk} />
              <span id="decl-hint" className="hint">
                {t("assess.declarationHint")}
              </span>
            </label>
            {touched && !textOk && <p className="hint warn-text">{t("assess.tooShort")}</p>}
            <VoiceInput
              forSelf
              language={lang}
              onText={(spoken) => {
                setText((prev) => (prev.trim() ? `${prev.trim()}\n${spoken}` : spoken));
                setUsedVoice(true);
                setReadBack(false);
              }}
            />
            {usedVoice && (
              <label className="check">
                <input type="checkbox" checked={readBack} onChange={(e) => setReadBack(e.target.checked)} />
                <span>{t("assess.checkedText")}</span>
              </label>
            )}
            {touched && usedVoice && !readBack && <p className="hint warn-text">{t("assess.checkTextFirst")}</p>}
            <label className="field">
              <span className="label">{t("assess.date")}</span>
              <input type="date" min={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
              <span className="hint">{t("assess.dateHint")}</span>
            </label>
            <ErrorBox error={error} />
            <button type="submit" className="btn btn-primary btn-block btn-big" disabled={busy}>
              {busy ? t("common.wait") : t("assess.send")}
            </button>
          </form>
        )
      )}
      <p className="fine-print">{t("assess.principle")}</p>
    </div>
  );
}
