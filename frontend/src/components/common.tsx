import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { clamp01 } from "../util";

export function SampleBadge({ show = true }: { show?: boolean }) {
  const { t } = useI18n();
  if (!show) return null;
  return (
    <span className="badge badge-sample" title={t("common.sampleTitle")}>
      {t("common.sample")}
    </span>
  );
}

export function PendingBadge({ label }: { label?: string }) {
  const { t } = useI18n();
  return <span className="badge badge-pending">{label ?? t("common.pending")}</span>;
}

export function CriticalBadge() {
  const { t } = useI18n();
  return <span className="badge badge-critical">⚠ {t("common.critical")}</span>;
}

/** Horizontal bar for a 0..1 value, with an optional marker (e.g. the pass mark). */
export function Bar({
  value,
  marker,
  label,
  tone = "brand",
}: {
  value: number | null;
  marker?: number;
  label: string;
  tone?: "brand" | "warn" | "bad" | "ok";
}) {
  const v = value === null ? 0 : clamp01(value);
  return (
    <div
      className="bar"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={value ?? 0}
    >
      <div className={`bar-fill tone-${tone}`} style={{ width: `${v * 100}%` }} />
      {marker !== undefined && <div className="bar-marker" style={{ left: `${clamp01(marker) * 100}%` }} />}
    </div>
  );
}

export function Notice({
  kind = "info",
  children,
  role,
}: {
  kind?: "info" | "warn" | "error" | "ok";
  children: ReactNode;
  role?: "status" | "alert";
}) {
  return (
    <div className={`notice notice-${kind}`} role={role}>
      {children}
    </div>
  );
}

/** States that the photo model only checks presence of PPE/tools, never workmanship. */
export function PresenceNote() {
  const { t } = useI18n();
  return <Notice kind="info">📷 {t("common.presenceOnly")}</Notice>;
}

export function Loading() {
  const { t } = useI18n();
  return (
    <p className="muted" role="status">
      {t("common.loading")}
    </p>
  );
}

export function ErrorText({ error }: { error: string | null | undefined }) {
  const { t } = useI18n();
  if (!error) return null;
  return (
    <Notice kind="error" role="alert">
      {t("common.error", { msg: error })}
    </Notice>
  );
}
