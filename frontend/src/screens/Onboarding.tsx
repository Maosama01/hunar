// First run: language -> who are you -> 2-3 intro cards -> itemised consent -> register (-> SMS code).
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, type AuthConfig, type OtpOut } from "../api";
import { normalisePhone, OtpInput, PhoneInput, pinProblem, PinInput } from "../components/AuthInputs";
import { Notice } from "../components/common";
import { Icon, type IconName } from "../components/Icon";
import { LanguageGrid } from "../components/LanguageGrid";
import { TranslationBanner } from "../components/Layout";
import { ErrorBox, Ltr, SpeakButton, Switch, useLoad } from "../components/ui";
import { orderedPurposes, usePurposeText } from "../consent";
import { enText, hasChosenLanguage, useI18n, type Key } from "../i18n";
import { acknowledgeEnded, homePath, setSession, useSession } from "../session";

type Step = "lang" | "role" | "intro" | "consent" | "register" | "otp";
type PublicRole = "worker" | "customer";
const STEPS: Step[] = ["lang", "role", "intro", "consent", "register"];

const INTRO: Record<PublicRole, { icon: IconName; title: Key; body: Key }[]> = {
  worker: [
    { icon: "quiz", title: "intro.w1.title", body: "intro.w1.body" },
    { icon: "clipboard", title: "intro.w2.title", body: "intro.w2.body" },
    { icon: "calendar", title: "intro.w3.title", body: "intro.w3.body" },
  ],
  customer: [
    { icon: "search", title: "intro.c1.title", body: "intro.c1.body" },
    { icon: "check", title: "intro.c2.title", body: "intro.c2.body" },
    { icon: "phone", title: "intro.c3.title", body: "intro.c3.body" },
  ],
};

function Progress({ step }: { step: Step }) {
  const { t } = useI18n();
  const i = Math.max(0, STEPS.indexOf(step === "otp" ? "register" : step));
  return (
    <div className="onb-progress" aria-label={t("onb.stepOf", { n: i + 1, total: STEPS.length })}>
      {STEPS.map((s, k) => (
        <span key={s} className={`onb-dot ${k <= i ? "on" : ""}`} />
      ))}
    </div>
  );
}

export function Onboarding() {
  const { t, lang, langOf } = useI18n();
  const navigate = useNavigate();
  const session = useSession();
  const [params] = useSearchParams();
  const replay = params.get("replay") === "1";
  const paramRole = params.get("role");
  const [role, setRole] = useState<PublicRole | null>(paramRole === "worker" || paramRole === "customer" ? paramRole : null);
  const firstStep = (params.get("step") as Step | null) ?? (hasChosenLanguage() ? "role" : "lang");
  const [step, setStep] = useState<Step>(firstStep === "intro" && !role ? "role" : firstStep);
  const [introIdx, setIntroIdx] = useState(0);
  const cfg = useLoad(() => api.authConfig(), []);

  // Registration form state lives here so Back does not lose it.
  const [consents, setConsents] = useState<Record<string, boolean>>({});
  const [adult, setAdult] = useState(false);
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [pin2, setPin2] = useState("");
  const [otp, setOtp] = useState<OtpOut | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [exists, setExists] = useState(false);
  /** Where to go right after registering (the logged-in redirect below uses it). */
  const registeredTo = useRef<string | null>(null);

  useEffect(() => {
    window.scrollTo(0, 0);
    setError(null);
  }, [step, introIdx]);

  if (session.account && !replay) {
    const to = registeredTo.current;
    return <Navigate to={to ?? homePath(session.account)} replace state={to ? { welcome: true } : undefined} />;
  }

  const ended = session.ended;
  const back = () => {
    const prev: Partial<Record<Step, Step>> = { role: "lang", intro: "role", consent: "intro", register: "consent", otp: "register" };
    if (step === "intro" && introIdx > 0) setIntroIdx(introIdx - 1);
    else if (prev[step]) setStep(prev[step]!);
  };

  const finishIntro = () => {
    if (replay) navigate(homePath(session.account), { replace: true });
    else setStep("consent");
  };

  // ---------------------------------------------------------------------------------------------
  let body;
  if (step === "lang") {
    body = (
      <>
        <h1>{t("onb.chooseLang")}</h1>
        {lang !== "en" && <p className="muted" lang="en">{enText("onb.chooseLang")}</p>}
        <LanguageGrid />
        <button type="button" className="btn btn-primary btn-block btn-big" onClick={() => setStep("role")}>
          {t("common.next")}
        </button>
      </>
    );
  } else if (step === "role") {
    body = (
      <>
        <h1>{t("onb.whoAreYou")}</h1>
        {ended === "erased" && <Notice kind="ok">{t("privacy.erased")}</Notice>}
        <div className="role-cards">
          {(["worker", "customer"] as const).map((r) => (
            <button
              key={r}
              type="button"
              className={`role-card ${role === r ? "on" : ""}`}
              onClick={() => {
                setRole(r);
                setIntroIdx(0);
                setConsents({});
                setStep("intro");
                acknowledgeEnded();
              }}
            >
              <span className="role-icon" aria-hidden="true">
                <Icon name={r === "worker" ? "briefcase" : "home"} size={40} />
              </span>
              <span className="role-title">{t(r === "worker" ? "onb.worker" : "onb.customer")}</span>
              <span className="role-sub">{t(r === "worker" ? "onb.workerDesc" : "onb.customerDesc")}</span>
            </button>
          ))}
        </div>
        <Link to="/login" className="btn btn-block">
          {t("onb.haveAccount")}
        </Link>
        <p className="center">
          <Link to="/login?staff=1" className="small">
            {t("onb.staffLogin")}
          </Link>
        </p>
      </>
    );
  } else if (step === "intro" && role) {
    const cards = INTRO[role];
    const c = cards[introIdx];
    const last = introIdx === cards.length - 1;
    body = (
      <>
        <div className="intro-card" aria-live="polite">
          <span className="intro-icon" aria-hidden="true">
            <Icon name={c.icon} size={56} />
          </span>
          <h1>{t(c.title)}</h1>
          <p className="intro-body">{t(c.body)}</p>
          <SpeakButton text={`${t(c.title)}. ${t(c.body)}`} lang={langOf(c.body)} />
        </div>
        <div className="intro-dots" aria-hidden="true">
          {cards.map((_, k) => (
            <span key={k} className={`onb-dot ${k === introIdx ? "on" : ""}`} />
          ))}
        </div>
        <button
          type="button"
          className="btn btn-primary btn-block btn-big"
          onClick={() => (last ? finishIntro() : setIntroIdx(introIdx + 1))}
        >
          {last ? (replay ? t("common.done") : t("onb.getStarted")) : t("common.next")}
        </button>
        {!last && (
          <button type="button" className="btn btn-ghost btn-block" onClick={finishIntro}>
            {t("onb.skip")}
          </button>
        )}
        {role === "customer" && !replay && (
          <p className="center">
            <Link to="/c/find" className="small">
              {t("onb.lookFirst")}
            </Link>
          </p>
        )}
      </>
    );
  } else if (step === "consent" && role) {
    body = (
      <ConsentStep
        cfg={cfg.data}
        cfgError={cfg.error}
        role={role}
        consents={consents}
        setConsents={setConsents}
        adult={adult}
        setAdult={setAdult}
        onNext={() => setStep("register")}
      />
    );
  } else if ((step === "register" || step === "otp") && role && cfg.data) {
    const config = cfg.data;
    const phone10 = normalisePhone(phone);
    const pinErr = pin ? pinProblem(pin, phone10) : null;
    const nameOk = name.trim().length >= 1 && name.trim().length <= 40;
    const formOk = !!phone10 && nameOk && !pinErr && pin.length >= 4 && pin === pin2;

    const register = async (challenge?: OtpOut) => {
      setBusy(true);
      setError(null);
      setExists(false);
      try {
        const res = await api.register({
          phone: phone10!,
          pin,
          role,
          display_name: name.trim(),
          language: config.languages.includes(lang) ? lang : "en",
          is_adult: adult,
          consents,
          otp_challenge_id: challenge?.challenge_id,
          otp_code: challenge ? code : undefined,
        });
        registeredTo.current = role === "worker" ? "/w/profile" : "/c/find";
        setSession(res.token, res.account); // the redirect above then opens registeredTo
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) setExists(true);
        else setError(e);
      } finally {
        setBusy(false);
      }
    };

    const sendCode = async () => {
      setBusy(true);
      setError(null);
      try {
        const o = await api.requestOtp(phone10!, "register");
        setOtp(o);
        setCode("");
        setStep("otp");
      } catch (e) {
        setError(e);
      } finally {
        setBusy(false);
      }
    };

    const submit = (e: FormEvent) => {
      e.preventDefault();
      if (!formOk) return;
      if (config.otp_required) void sendCode();
      else void register();
    };

    body =
      step === "register" ? (
        <form className="stack" onSubmit={submit} noValidate>
          <h1>{t(role === "worker" ? "reg.titleWorker" : "reg.titleCustomer")}</h1>
          <PhoneInput value={phone} onChange={setPhone} invalid={!!phone && !phone10} autoFocus />
          {phone && !phone10 && <p className="hint warn-text">{t("auth.phoneInvalid")}</p>}
          <label className="field">
            <span className="label">{t("reg.name")}</span>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={40} autoComplete="nickname" aria-describedby="name-hint" />
            <span id="name-hint" className="hint">
              {t("reg.nameHint")}
            </span>
          </label>
          <PinInput label={t("reg.pin")} value={pin} onChange={setPin} invalid={!!pinErr} hint={t("reg.pinRules")} />
          {pinErr && <p className="hint warn-text" role="alert">{t(pinErr)}</p>}
          <PinInput label={t("reg.pin2")} value={pin2} onChange={setPin2} invalid={!!pin2 && pin2 !== pin} />
          {pin2 && pin2 !== pin && <p className="hint warn-text">{t("reg.pinMismatch")}</p>}
          <p className="small muted">{t("reg.pinRemember")}</p>
          {exists && (
            <Notice kind="warn" role="alert">
              {t("reg.exists")} <Link to="/login">{t("auth.loginInstead")}</Link>
            </Notice>
          )}
          <ErrorBox error={error} />
          <button type="submit" className="btn btn-primary btn-block btn-big" disabled={!formOk || busy}>
            {busy ? t("common.wait") : config.otp_required ? t("reg.sendCode") : t("reg.create")}
          </button>
        </form>
      ) : (
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.length === 6 && otp) void register(otp);
          }}
          noValidate
        >
          <h1>{t("otp.title")}</h1>
          <p>
            {t("otp.sentTo")} <Ltr>+91 {phone10}</Ltr>
          </p>
          {otp?.test_code && (
            <Notice kind="warn" role="status">
              <strong>{t("otp.testMode")}</strong> {t("otp.testCode")} <Ltr><code className="big-code">{otp.test_code}</code></Ltr>
              {otp.test_note && <span className="block small" lang="en">{otp.test_note}</span>}
            </Notice>
          )}
          <OtpInput value={code} onChange={setCode} />
          {exists && (
            <Notice kind="warn" role="alert">
              {t("reg.exists")} <Link to="/login">{t("auth.loginInstead")}</Link>
            </Notice>
          )}
          <ErrorBox error={error} />
          <button type="submit" className="btn btn-primary btn-block btn-big" disabled={code.length !== 6 || busy}>
            {busy ? t("common.wait") : t("reg.create")}
          </button>
          <button type="button" className="btn btn-ghost btn-block" onClick={() => void sendCode()} disabled={busy}>
            {t("otp.resend")}
          </button>
        </form>
      );
  } else if (step === "register" || step === "otp") {
    body = cfg.error ? <ErrorBox error={cfg.error} /> : <p className="muted">{t("common.loading")}</p>;
  } else {
    body = null;
  }

  return (
    <div className="onb">
      <TranslationBanner />
      <div className="onb-top">
        {step !== "lang" && !(step === "role" && firstStep === "role") ? (
          <button type="button" className="btn btn-ghost" onClick={back}>
            <Icon name="chevron" className="flip" /> {t("common.back")}
          </button>
        ) : (
          <span />
        )}
        {!replay && <Progress step={step} />}
        <Link to="/language" className="btn btn-small btn-ghost" aria-label={t("header.changeLang")}>
          <Icon name="globe" size={20} />
        </Link>
      </div>
      <div className="onb-body stack">{body}</div>
    </div>
  );
}

function ConsentStep({
  cfg,
  cfgError,
  role,
  consents,
  setConsents,
  adult,
  setAdult,
  onNext,
}: {
  cfg: AuthConfig | undefined;
  cfgError: unknown;
  role: PublicRole;
  consents: Record<string, boolean>;
  setConsents: (c: Record<string, boolean>) => void;
  adult: boolean;
  setAdult: (v: boolean) => void;
  onNext: () => void;
}) {
  const { t } = useI18n();
  const text = usePurposeText(cfg);
  if (cfgError) return <ErrorBox error={cfgError} />;
  if (!cfg) return <p className="muted">{t("common.loading")}</p>;
  const purposes = orderedPurposes(cfg.purposes[role]);
  const missingRequired = purposes.filter(([k, p]) => p.required && !consents[k]);
  const ok = missingRequired.length === 0 && adult;
  return (
    <div className="stack">
      <h1>{t("consent.title")}</h1>
      <p>{t("consent.intro")}</p>
      <p className="small muted">{t("consent.version", { v: cfg.notice_version })}</p>
      {purposes.map(([key, spec]) => {
        const tx = text(key, spec);
        return (
          <section key={key} className={`card consent-item ${spec.required ? "is-required" : ""}`}>
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
            <SpeakButton small text={`${tx.title}. ${tx.why}. ${tx.data}`} lang={tx.lang} />
            {spec.required ? (
              <>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={!!consents[key]}
                    onChange={(e) => setConsents({ ...consents, [key]: e.target.checked })}
                  />
                  <span>{t("consent.agree")}</span>
                </label>
                <p className="hint">{t("consent.requiredWhy")}</p>
              </>
            ) : (
              <Switch
                checked={!!consents[key]}
                onChange={(v) => setConsents({ ...consents, [key]: v })}
                label={<strong>{t("consent.allow")}</strong>}
              />
            )}
          </section>
        );
      })}
      <label className="check check-strong">
        <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
        <span>
          <strong>{t("consent.adult")}</strong>
          <span className="block small muted">{t("consent.adultWhy")}</span>
        </span>
      </label>
      {!ok && <p className="hint">{t("consent.needAll")}</p>}
      <button type="button" className="btn btn-primary btn-block btn-big" disabled={!ok} onClick={onNext}>
        {t("common.next")}
      </button>
    </div>
  );
}
