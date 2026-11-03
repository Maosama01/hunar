// Phone and PIN inputs with the same rules as backend/hunar/accounts/auth.py, so mistakes are shown
// before the request (the server checks again).
import { useId, useState } from "react";
import { useI18n, type Key } from "../i18n";
import { Icon } from "./Icon";

/** 10-digit Indian mobile number, or null. Accepts spaces, dashes, +91, 91 or 0 prefixes. */
export function normalisePhone(raw: string): string | null {
  let d = raw.replace(/[\s\-()]/g, "");
  if (d.startsWith("+")) d = d.slice(1);
  if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
  else if (d.length === 11 && d.startsWith("0")) d = d.slice(1);
  return /^[6-9]\d{9}$/.test(d) ? d : null;
}

/** Why a PIN is not acceptable (an i18n key), or null. */
export function pinProblem(pin: string, phone10: string | null): Key | null {
  if (!/^\d{4,6}$/.test(pin)) return "pin.ruleDigits";
  if (new Set(pin).size === 1) return "pin.ruleRepeat";
  const steps = new Set<number>();
  for (let i = 1; i < pin.length; i++) steps.add(Number(pin[i]) - Number(pin[i - 1]));
  if (steps.size === 1 && (steps.has(1) || steps.has(-1))) return "pin.ruleSequence";
  if (phone10 && phone10.endsWith(pin)) return "pin.rulePhoneEnd";
  return null;
}

export function PhoneInput({
  value,
  onChange,
  invalid,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  invalid?: boolean;
  autoFocus?: boolean;
}) {
  const { t } = useI18n();
  const id = useId();
  return (
    <label className="field" htmlFor={id}>
      <span className="label">{t("auth.phone")}</span>
      <div className="phone-row" dir="ltr">
        <span className="phone-prefix" aria-hidden="true">
          +91
        </span>
        <input
          id={id}
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={16}
          placeholder="98xxxxxx10"
          aria-invalid={invalid}
          aria-describedby={`${id}-hint`}
          autoFocus={autoFocus}
        />
      </div>
      <span id={`${id}-hint`} className="hint">
        {t("auth.phoneHint")}
      </span>
    </label>
  );
}

export function PinInput({
  label,
  value,
  onChange,
  invalid,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  invalid?: boolean;
  hint?: string;
}) {
  const { t } = useI18n();
  const id = useId();
  const [show, setShow] = useState(false);
  return (
    <div className="field">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <div className="pin-row" dir="ltr">
        <input
          id={id}
          className="pin-input"
          type={show ? "text" : "password"}
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          maxLength={6}
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
          aria-invalid={invalid}
          aria-describedby={hint ? `${id}-hint` : undefined}
        />
        <button
          type="button"
          className="btn btn-ghost pin-eye"
          onClick={() => setShow((s) => !s)}
          aria-pressed={show}
          aria-label={show ? t("auth.hidePin") : t("auth.showPin")}
        >
          <Icon name={show ? "eyeOff" : "eye"} />
        </button>
      </div>
      {hint && (
        <span id={`${id}-hint`} className="hint">
          {hint}
        </span>
      )}
    </div>
  );
}

export function OtpInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useI18n();
  const id = useId();
  return (
    <label className="field" htmlFor={id}>
      <span className="label">{t("otp.code")}</span>
      <input
        id={id}
        className="pin-input"
        dir="ltr"
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        autoComplete="one-time-code"
        maxLength={6}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
      />
    </label>
  );
}
