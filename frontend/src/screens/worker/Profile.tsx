// The worker's own profile, and exactly what customers will see.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, TRADES, type MyProfile, type Trade } from "../../api";
import { Loading, Notice } from "../../components/common";
import { Icon, TRADE_ICON } from "../../components/Icon";
import { BadgeExplain, WorkerCard } from "../../components/WorkerCard";
import { ErrorBox, useLoad } from "../../components/ui";
import { useI18n } from "../../i18n";
import { LANGUAGES } from "../../i18n/languages";
import { useSession } from "../../session";
import { useTrades } from "../../trades";
import { fmtDate } from "../../util";

const PINCODE = /^[1-9]\d{5}$/;

export function WorkerProfile() {
  const { t, lang, pick } = useI18n();
  const location = useLocation();
  const welcome = (location.state as { welcome?: boolean } | null)?.welcome;
  const { account } = useSession();
  const { trades } = useTrades();
  const prof = useLoad(() => api.myProfile(), []);
  const [form, setForm] = useState({
    trade: null as Trade | null,
    years: "",
    pincode: "",
    district: "",
    languages: [lang] as string[],
    bio: "",
    permit: false,
    permitState: "",
  });
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  // Each trade needs its quiz first (the server refuses the save otherwise).
  const quizzed = account?.quiz?.finished_trades ?? [];
  const needsQuiz = !!form.trade && !!account?.quiz && !quizzed.includes(form.trade);

  const fill = (p: MyProfile) =>
    setForm({
      trade: p.trade,
      years: String(p.years_experience),
      pincode: p.pincode,
      district: p.district,
      languages: p.languages ? p.languages.split(",").filter(Boolean) : [],
      bio: p.bio,
      permit: p.permit_status !== "none",
      permitState: p.permit_state,
    });

  useEffect(() => {
    if (prof.data) fill(prof.data);
    else if (prof.data === null && quizzed[0]) setForm((f) => (f.trade ? f : { ...f, trade: quizzed[0] }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prof.data]);

  const years = Number(form.years);
  const yearsOk = form.years !== "" && Number.isInteger(years) && years >= 0 && years <= 60;
  const pinOk = PINCODE.test(form.pincode);
  const ok = !!form.trade && yearsOk && pinOk && !needsQuiz;
  const checked = prof.data?.permit_status === "document_checked";
  const tradeChangeResetsPermit = checked && form.trade !== prof.data?.trade;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    setSaved(false);
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.saveProfile({
        trade: form.trade!,
        years_experience: years,
        pincode: form.pincode,
        district: form.district.trim(),
        languages: form.languages,
        bio: form.bio.trim(),
        permit_status: form.trade === "electrician" && form.permit ? "self_declared" : "none",
        permit_state: form.trade === "electrician" && form.permit ? form.permitState.trim() : "",
      });
      prof.setData(p);
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const toggleLang = (code: string) =>
    setForm((f) => ({ ...f, languages: f.languages.includes(code) ? f.languages.filter((x) => x !== code) : [...f.languages, code] }));

  if (prof.loading && prof.data === undefined) return <Loading />;
  const p = prof.data;
  const showConsent = !account?.consents.profile_display;

  return (
    <div className="stack">
      {welcome && <Notice kind="ok">{t("profile.welcome", { name: account?.display_name ?? "" })}</Notice>}
      <h1>{t("wprofile.title")}</h1>
      <ErrorBox error={prof.error} />
      {!p && !prof.error && <p>{t("wprofile.intro")}</p>}

      {p && (
        <section className="card stack">
          <h2>{t("wprofile.preview")}</h2>
          {p.visible ? (
            <Notice kind="ok">{t("wprofile.visible")}</Notice>
          ) : (
            <Notice kind="warn">
              {t("wprofile.hidden")} <Link to="/w/privacy">{t("nav.privacy")}</Link>
            </Notice>
          )}
          <div className="preview-frame">
            <WorkerCard p={p.public} detailed />
            <BadgeExplain p={p.public} />
          </div>
          <p className="hint">{t("wprofile.previewNote")}</p>
        </section>
      )}
      {!p && showConsent && (
        <Notice kind="info">
          {t("wprofile.consentFirst")} <Link to="/w/privacy">{t("nav.privacy")}</Link>
        </Notice>
      )}

      <form className="card stack" onSubmit={(e) => void save(e)} noValidate>
        <h2>{p ? t("wprofile.edit") : t("wprofile.create")}</h2>
        <fieldset className="field">
          <legend className="label">{t("wprofile.trade")}</legend>
          <div className="chip-grid" role="radiogroup">
            {TRADES.map((tr) => (
              <button
                key={tr}
                type="button"
                role="radio"
                aria-checked={form.trade === tr}
                className={`trade-chip ${form.trade === tr ? "on" : ""}`}
                onClick={() => setForm((f) => ({ ...f, trade: tr }))}
              >
                <Icon name={TRADE_ICON[tr]} size={28} />
                <span>{trades ? pick(trades[tr]?.name) : t(`trade.${tr}`)}</span>
              </button>
            ))}
          </div>
          {touched && !form.trade && <p className="hint warn-text">{t("wprofile.tradeRequired")}</p>}
        </fieldset>
        {needsQuiz && (
          <Notice kind="warn">
            {t("wprofile.quizFirst", { trade: trades ? pick(trades[form.trade!]?.name) : t(`trade.${form.trade!}`) })}{" "}
            <Link to="/w/quiz">{t("wprofile.takeQuiz")}</Link>
          </Notice>
        )}
        {tradeChangeResetsPermit && <Notice kind="warn">{t("wprofile.tradeResetsPermit")}</Notice>}

        <div className="two-col">
          <label className="field">
            <span className="label">{t("wprofile.years")}</span>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={60}
              value={form.years}
              onChange={(e) => setForm((f) => ({ ...f, years: e.target.value }))}
              aria-invalid={touched && !yearsOk}
            />
          </label>
          <label className="field">
            <span className="label">{t("wprofile.pincode")}</span>
            <input
              type="text"
              inputMode="numeric"
              dir="ltr"
              maxLength={6}
              value={form.pincode}
              onChange={(e) => setForm((f) => ({ ...f, pincode: e.target.value.replace(/\D/g, "").slice(0, 6) }))}
              aria-invalid={touched && !pinOk}
            />
          </label>
        </div>
        {touched && !yearsOk && <p className="hint warn-text">{t("wprofile.yearsInvalid")}</p>}
        {touched && !pinOk && <p className="hint warn-text">{t("common.pincodeInvalid")}</p>}
        <p className="hint">{t("wprofile.pincodeHint")}</p>

        <label className="field">
          <span className="label">{t("wprofile.district")}</span>
          <input type="text" maxLength={60} value={form.district} onChange={(e) => setForm((f) => ({ ...f, district: e.target.value }))} />
        </label>

        <fieldset className="field">
          <legend className="label">{t("wprofile.languages")}</legend>
          <div className="lang-chips">
            {LANGUAGES.map((l) => (
              <label key={l.code} className={`lang-chip ${form.languages.includes(l.code) ? "on" : ""}`}>
                <input type="checkbox" checked={form.languages.includes(l.code)} onChange={() => toggleLang(l.code)} />
                <span lang={l.htmlLang} dir={l.dir}>
                  {l.endonym}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <label className="field">
          <span className="label">{t("wprofile.bio")}</span>
          <textarea rows={3} maxLength={300} value={form.bio} onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))} aria-describedby="bio-hint" />
          <span id="bio-hint" className="hint">
            {t("wprofile.bioHint", { n: 300 - form.bio.length })}
          </span>
        </label>

        {form.trade === "electrician" && (
          <fieldset className="field stack-s">
            <legend className="label">{t("wprofile.permit")}</legend>
            {checked && !tradeChangeResetsPermit ? (
              <Notice kind="ok">
                {t("wprofile.permitChecked", { state: p?.permit_state || "?", date: fmtDate(p?.permit_checked_at, lang) })}
              </Notice>
            ) : (
              <>
                <label className="check">
                  <input type="checkbox" checked={form.permit} onChange={(e) => setForm((f) => ({ ...f, permit: e.target.checked }))} />
                  <span>{t("wprofile.permitHave")}</span>
                </label>
                {form.permit && (
                  <label className="field">
                    <span className="label">{t("wprofile.permitState")}</span>
                    <input type="text" maxLength={40} value={form.permitState} onChange={(e) => setForm((f) => ({ ...f, permitState: e.target.value }))} />
                  </label>
                )}
                <p className="hint">{t("wprofile.permitHint")}</p>
              </>
            )}
          </fieldset>
        )}

        <ErrorBox error={error} />
        {saved && (
          <Notice kind="ok" role="status">
            {t("wprofile.saved")}
          </Notice>
        )}
        <button type="submit" className="btn btn-primary btn-block btn-big" disabled={busy || needsQuiz}>
          {busy ? t("common.wait") : t("wprofile.save")}
        </button>
      </form>
    </div>
  );
}
