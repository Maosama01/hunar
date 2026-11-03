// Consent per purpose (withdraw as easily as given) and erasing the account.
import { useState } from "react";
import { api } from "../api";
import { Loading, Notice } from "../components/common";
import { Icon } from "../components/Icon";
import { ErrorBox, SpeakButton, Switch, useLoad } from "../components/ui";
import { orderedPurposes, usePurposeText } from "../consent";
import { enText, useI18n } from "../i18n";
import { clearSession, updateAccount, useSession } from "../session";

export function PrivacyScreen() {
  const { t } = useI18n();
  const { account } = useSession();
  const cfg = useLoad(() => api.authConfig(), []);
  const me = useLoad(async () => {
    const a = await api.me();
    updateAccount(a);
    return a;
  }, []);
  const text = usePurposeText(cfg.data);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [confirmOff, setConfirmOff] = useState<string | null>(null);
  const [word, setWord] = useState("");
  const [erasing, setErasing] = useState(false);

  if (!account) return null;
  const consents = me.data?.consents ?? account.consents;
  const purposes = orderedPurposes(cfg.data?.purposes[account.role]);

  const setConsent = async (purpose: string, granted: boolean) => {
    setBusy(purpose);
    setError(null);
    setConfirmOff(null);
    try {
      const a = await api.setConsent(purpose, granted);
      updateAccount(a);
      me.setData(a);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  const eraseWords = [t("privacy.eraseWord"), enText("privacy.eraseWord")].map((w) => w.trim().toLowerCase());
  const wordOk = eraseWords.includes(word.trim().toLowerCase());
  const erase = async () => {
    setErasing(true);
    setError(null);
    try {
      await api.eraseMe();
      clearSession("erased", "/welcome?step=role"); // the route guard goes there
    } catch (e) {
      setError(e);
      setErasing(false);
    }
  };

  return (
    <div className="stack">
      <h1>{t("privacy.title")}</h1>
      <p>{t("privacy.intro")}</p>
      <ErrorBox error={cfg.error ?? me.error} />
      {!cfg.data && cfg.loading && <Loading />}
      {cfg.data && <p className="small muted">{t("consent.version", { v: cfg.data.notice_version })}</p>}
      <ErrorBox error={error} />
      {purposes.map(([key, spec]) => {
        const tx = text(key, spec);
        const on = !!consents[key];
        return (
          <section key={key} className="card consent-item stack-s">
            <div className="row wrap gap-s between">
              <h2 className="h-inline">{tx.title}</h2>
              <span className={`badge ${spec.required ? "badge-required" : ""}`}>
                {spec.required ? t("consent.required") : t("consent.optional")}
              </span>
            </div>
            <p lang={tx.lang}>
              <strong>{t("consent.why")}</strong> {tx.why}
            </p>
            <p className="small" lang={tx.lang}>
              <strong>{t("consent.data")}</strong> {tx.data}
            </p>
            <p className="small muted" lang={tx.lang}>
              <strong>{t("consent.withdraw")}</strong> {tx.withdraw}
            </p>
            <SpeakButton small text={`${tx.title}. ${tx.why}`} lang={tx.lang} />
            {spec.required ? (
              <p className="small">
                <Icon name="lock" size={16} /> {t("privacy.requiredOn")}
              </p>
            ) : confirmOff === key ? (
              <Notice kind="warn" role="alert">
                <p>{t("privacy.confirmOff", { what: tx.withdraw })}</p>
                <div className="row wrap gap">
                  <button type="button" className="btn btn-danger" disabled={!!busy} onClick={() => void setConsent(key, false)}>
                    {t("privacy.turnOff")}
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => setConfirmOff(null)}>
                    {t("common.cancel")}
                  </button>
                </div>
              </Notice>
            ) : (
              <Switch
                checked={on}
                disabled={busy === key}
                onChange={(v) => (v ? void setConsent(key, true) : setConfirmOff(key))}
                label={<strong>{on ? t("privacy.on") : t("privacy.off")}</strong>}
              />
            )}
          </section>
        );
      })}

      <section className="card card-bad stack-s">
        <h2>
          <Icon name="trash" /> {t("privacy.eraseTitle")}
        </h2>
        <p>{t("privacy.eraseExplain")}</p>
        {!erasing && (
          <>
            <label className="field">
              <span className="label">{t("privacy.eraseType", { word: t("privacy.eraseWord") })}</span>
              <input type="text" value={word} onChange={(e) => setWord(e.target.value)} autoComplete="off" />
            </label>
            <button type="button" className="btn btn-danger btn-block" disabled={!wordOk} onClick={() => void erase()}>
              {t("privacy.eraseButton")}
            </button>
          </>
        )}
        {erasing && <p className="muted">{t("common.wait")}</p>}
      </section>
    </div>
  );
}
