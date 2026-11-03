// Forgot PIN: an SMS code when the server has one set up, otherwise ask an admin.
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type OtpOut } from "../api";
import { normalisePhone, OtpInput, PhoneInput, pinProblem, PinInput } from "../components/AuthInputs";
import { Notice } from "../components/common";
import { Icon } from "../components/Icon";
import { ErrorBox, Ltr, useLoad } from "../components/ui";
import { useI18n } from "../i18n";

export function ResetPin() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const cfg = useLoad(() => api.authConfig(), []);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState<OtpOut | null>(null);
  const [code, setCode] = useState("");
  const [pin, setPin] = useState("");
  const [pin2, setPin2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const phone10 = normalisePhone(phone);
  const pinErr = pin ? pinProblem(pin, phone10) : null;

  const sendCode = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!phone10) return;
    setBusy(true);
    setError(null);
    try {
      setOtp(await api.requestOtp(phone10, "reset"));
      setCode("");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const reset = async (e: FormEvent) => {
    e.preventDefault();
    if (!otp?.challenge_id || !phone10 || pinErr || pin !== pin2 || code.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      await api.resetPin({ phone: phone10, new_pin: pin, otp_challenge_id: otp.challenge_id, otp_code: code });
      navigate("/login", { replace: true, state: { reset: true } });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onb">
      <div className="onb-top">
        <Link to="/login" className="btn btn-ghost">
          <Icon name="chevron" className="flip" /> {t("common.back")}
        </Link>
      </div>
      <div className="onb-body stack">
        <h1>{t("reset.title")}</h1>
        {cfg.data && !cfg.data.otp_required && <Notice kind="info">{t("login.askAdmin")}</Notice>}
        <ErrorBox error={cfg.error} />
        {cfg.data?.otp_required && !otp && (
          <form className="stack" onSubmit={(e) => void sendCode(e)} noValidate>
            <PhoneInput value={phone} onChange={setPhone} invalid={!!phone && !phone10} autoFocus />
            <ErrorBox error={error} />
            <button type="submit" className="btn btn-primary btn-block btn-big" disabled={!phone10 || busy}>
              {busy ? t("common.wait") : t("reg.sendCode")}
            </button>
          </form>
        )}
        {otp && (
          <form className="stack" onSubmit={(e) => void reset(e)} noValidate>
            <p>
              {t("otp.sentTo")} <Ltr>+91 {phone10}</Ltr>
            </p>
            {otp.test_code && (
              <Notice kind="warn" role="status">
                <strong>{t("otp.testMode")}</strong> {t("otp.testCode")} <Ltr><code className="big-code">{otp.test_code}</code></Ltr>
                {otp.test_note && <span className="block small" lang="en">{otp.test_note}</span>}
              </Notice>
            )}
            <OtpInput value={code} onChange={setCode} />
            <PinInput label={t("reset.newPin")} value={pin} onChange={setPin} invalid={!!pinErr} hint={t("reg.pinRules")} />
            {pinErr && <p className="hint warn-text">{t(pinErr)}</p>}
            <PinInput label={t("reg.pin2")} value={pin2} onChange={setPin2} invalid={!!pin2 && pin2 !== pin} />
            {pin2 && pin2 !== pin && <p className="hint warn-text">{t("reg.pinMismatch")}</p>}
            <p className="small muted">{t("reset.logsOut")}</p>
            <ErrorBox error={error} />
            <button
              type="submit"
              className="btn btn-primary btn-block btn-big"
              disabled={busy || code.length !== 6 || !!pinErr || pin.length < 4 || pin !== pin2}
            >
              {busy ? t("common.wait") : t("reset.submit")}
            </button>
            <button type="button" className="btn btn-ghost btn-block" onClick={() => void sendCode()} disabled={busy}>
              {t("otp.resend")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
