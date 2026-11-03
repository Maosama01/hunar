import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { normalisePhone, PhoneInput, PinInput } from "../components/AuthInputs";
import { Notice } from "../components/common";
import { Icon } from "../components/Icon";
import { TranslationBanner } from "../components/Layout";
import { ErrorBox, useLoad } from "../components/ui";
import { useQueueCounts } from "../data";
import { hasChosenLanguage, useI18n } from "../i18n";
import { isLangCode } from "../i18n/languages";
import { acknowledgeEnded, homePath, setSession, useSession } from "../session";

export function Login() {
  const { t, setLang } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const staff = params.get("staff") === "1";
  const session = useSession();
  const counts = useQueueCounts();
  const cfg = useLoad(() => api.authConfig(), []);
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [known, setKnown] = useState<"wrong" | "locked" | null>(null);
  const [forgot, setForgot] = useState(false);
  const from = (location.state as { from?: string } | null)?.from;
  const resetDone = (location.state as { reset?: boolean } | null)?.reset;

  if (session.account) return <Navigate to={from ?? homePath(session.account)} replace />;

  const phone10 = normalisePhone(phone);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!phone10 || pin.length < 4) return;
    setBusy(true);
    setError(null);
    setKnown(null);
    try {
      const res = await api.login(phone10, pin);
      if (!hasChosenLanguage() && isLangCode(res.account.language)) setLang(res.account.language);
      acknowledgeEnded();
      setSession(res.token, res.account);
      navigate(from ?? homePath(res.account), { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setKnown("wrong");
      else if (err instanceof ApiError && err.status === 429) setKnown("locked");
      else setError(err);
      setPin("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onb">
      <TranslationBanner />
      <div className="onb-top">
        <Link to="/welcome" className="btn btn-ghost">
          <Icon name="chevron" className="flip" /> {t("common.back")}
        </Link>
        <span />
        <Link to="/language" className="btn btn-small btn-ghost" aria-label={t("header.changeLang")}>
          <Icon name="globe" size={20} />
        </Link>
      </div>
      <form className="onb-body stack" onSubmit={(e) => void submit(e)} noValidate>
        <h1>{staff ? t("login.staffTitle") : t("login.title")}</h1>
        {staff && <p className="muted">{t("login.staffNote")}</p>}
        {session.ended === "expired" && (
          <Notice kind="warn" role="status">
            {t("login.expired")}
          </Notice>
        )}
        {(counts?.ops ?? 0) > 0 && <Notice kind="info">{t("login.queuedKept", { n: counts!.ops })}</Notice>}
        {resetDone && <Notice kind="ok">{t("reset.done")}</Notice>}
        <PhoneInput value={phone} onChange={setPhone} invalid={!!phone && !phone10} autoFocus />
        {phone && !phone10 && <p className="hint warn-text">{t("auth.phoneInvalid")}</p>}
        <PinInput label={t("auth.pin")} value={pin} onChange={setPin} />
        {known === "wrong" && (
          <Notice kind="error" role="alert">
            {t("login.wrong")}
          </Notice>
        )}
        {known === "locked" && (
          <Notice kind="error" role="alert">
            {t("login.locked")}
          </Notice>
        )}
        <ErrorBox error={error} />
        <button type="submit" className="btn btn-primary btn-block btn-big" disabled={!phone10 || pin.length < 4 || busy}>
          {busy ? t("common.wait") : t("login.submit")}
        </button>
        <button type="button" className="btn btn-ghost btn-block" onClick={() => setForgot((f) => !f)} aria-expanded={forgot}>
          {t("login.forgot")}
        </button>
        {forgot &&
          (cfg.data?.otp_required ? (
            <Link to="/reset-pin" className="btn btn-block">
              {t("login.resetBySms")}
            </Link>
          ) : (
            <Notice kind="info">{cfg.data ? t("login.askAdmin") : t("common.loading")}</Notice>
          ))}
        {!staff && (
          <p className="center">
            {t("login.newHere")} <Link to="/welcome?step=role">{t("login.createAccount")}</Link>
          </p>
        )}
        {!staff && (
          <p className="center">
            <Link to="/login?staff=1" className="small">
              {t("onb.staffLogin")}
            </Link>
          </p>
        )}
        {staff && (
          <p className="center small">
            <Link to="/rater">{t("login.raterLink")}</Link>
          </p>
        )}
      </form>
    </div>
  );
}
