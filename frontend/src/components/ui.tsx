// Shared pieces for the worker and customer screens.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, errorText, NetworkError } from "../api";
import { useI18n } from "../i18n";
import { isConnected, useStatus } from "../status";
import { useTts } from "../tts";
import { Icon } from "./Icon";
import { Notice } from "./common";

/** Read-aloud button; renders nothing when the device has no voice for `lang`. */
export function SpeakButton({ text, lang, label, small }: { text: string; lang: string; label?: string; small?: boolean }) {
  const { t } = useI18n();
  const tts = useTts(lang);
  if (!tts.available || !text.trim()) return null;
  return (
    <button
      type="button"
      className={`btn btn-ghost speak ${small ? "btn-small" : ""}`}
      onClick={() => (tts.speaking ? tts.stop() : void tts.speak(text))}
      aria-pressed={tts.speaking}
    >
      <Icon name={tts.speaking ? "stop" : "volume"} size={20} />
      <span>{tts.speaking ? t("tts.stop") : label ?? t("tts.read")}</span>
    </button>
  );
}

/** Translate errors we can explain; otherwise show the server's own message. */
export function useErrorText(): (e: unknown) => string {
  const { t } = useI18n();
  return useCallback(
    (e: unknown) => {
      if (e instanceof NetworkError) return t("common.noNetwork");
      if (e instanceof ApiError && e.status === 401) return t("common.loginAgain");
      if (e instanceof ApiError && e.status === 403) return t("common.notAllowed");
      return errorText(e);
    },
    [t],
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const toText = useErrorText();
  if (error === null || error === undefined) return null;
  return (
    <Notice kind="error" role="alert">
      {toText(error)}
    </Notice>
  );
}

/** Load data from the API with loading / error state and a reload function. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const reload = useCallback(async () => {
    const my = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const v = await fn();
      if (my === seq.current) setData(v);
    } catch (e) {
      if (my === seq.current) setError(e);
    } finally {
      if (my === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

/** Worker and customer screens need the network; staff screens have the offline outbox instead. */
export function OfflineNotice() {
  const { t } = useI18n();
  const connected = isConnected(useStatus());
  if (connected) return null;
  return (
    <Notice kind="warn" role="status">
      <span className="row gap-s">
        <Icon name="wifiOff" size={20} />
        <span>{t("common.offlineFriendly")}</span>
      </span>
    </Notice>
  );
}

export function Stars({ value, count }: { value: number | null; count?: number }) {
  const { t } = useI18n();
  if (value === null) return <span className="muted small">{t("rating.none")}</span>;
  const full = Math.round(value);
  return (
    <span className="stars" aria-label={t("rating.aria", { v: value.toFixed(1), n: count ?? 0 })}>
      <span aria-hidden="true">
        {"★".repeat(full)}
        <span className="stars-off">{"★".repeat(Math.max(0, 5 - full))}</span>
      </span>{" "}
      <span className="small">
        {value.toFixed(1)}
        {count !== undefined && ` (${count})`}
      </span>
    </span>
  );
}

export function StarInput({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const { t } = useI18n();
  return (
    <div className="star-input" role="radiogroup" aria-label={t("rating.choose")}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={t("rating.nStars", { n })}
          className={`star-btn ${n <= value ? "on" : ""}`}
          onClick={() => onChange(n)}
        >
          ★
        </button>
      ))}
    </div>
  );
}

/** On/off switch with a visible label. */
export function Switch({
  checked,
  onChange,
  label,
  disabled,
  describedBy,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
  disabled?: boolean;
  describedBy?: string;
}) {
  return (
    <label className={`switch-row ${disabled ? "is-disabled" : ""}`}>
      <span className="grow">{label}</span>
      <input
        type="checkbox"
        role="switch"
        className="switch"
        checked={checked}
        disabled={disabled}
        aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}

/** Empty state: icon, one sentence, optional action. */
export function Empty({ icon, text, children }: { icon: Parameters<typeof Icon>[0]["name"]; text: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} size={40} />
      <p>{text}</p>
      {children}
    </div>
  );
}

/** Numbers like NSQF 3.0 shown as "3". */
export function num(x: number | null | undefined): string {
  if (x === null || x === undefined) return "";
  return Number.isInteger(x) ? String(x) : String(Math.round(x * 10) / 10);
}

/** Phone numbers and other Latin-digit strings keep their order inside right-to-left text. */
export function Ltr({ children }: { children: ReactNode }) {
  return <bdi dir="ltr">{children}</bdi>;
}
