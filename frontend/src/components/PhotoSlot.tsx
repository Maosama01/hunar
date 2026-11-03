import { useEffect, useId, useRef, useState } from "react";
import { addPhoto } from "../actions";
import { errorText, fetchBlob, intFromApi, type LabelledItem } from "../api";
import type { EvidenceView } from "../data";
import { useI18n } from "../i18n";
import { preparePhoto, type PreparedPhoto } from "../photo";
import { Notice, PendingBadge } from "./common";

/** Evidence images need the staff login, which an <img src> cannot send: fetch with the token and
 * show a blob URL (the service worker still caches the response for offline use). */
function useAuthedImage(url: string | null): string | null {
  const [obj, setObj] = useState<string | null>(null);
  useEffect(() => {
    if (!url) return;
    let alive = true;
    let made: string | null = null;
    void fetchBlob(url).then((b) => {
      if (!alive || !b) return;
      made = URL.createObjectURL(b);
      setObj(made);
    });
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [url]);
  return obj;
}

function EvidenceCard({ ev, slotLabel }: { ev: EvidenceView; slotLabel: string }) {
  const { t } = useI18n();
  const s = ev.server;
  const full = useAuthedImage(ev.imageUrl);
  const src = ev.thumb ?? full;
  return (
    <figure className="evidence">
      {src && (
        <a href={full ?? undefined} target="_blank" rel="noreferrer" aria-label={t("tasks.openFull")} onClick={(e) => !full && e.preventDefault()}>
          <img src={src} alt={t("tasks.photoAlt", { slot: slotLabel })} loading="lazy" />
        </a>
      )}
      <figcaption className="small stack-s">
        {s && <span className="muted">{t("tasks.evidence", { id: s.id })}</span>}
        {ev.pending && (
          <>
            <PendingBadge />
            <span className="hint">🔒 {t("tasks.localOnly")}</span>
          </>
        )}
        {s && <span>🙂 {t("tasks.facesBlurred", { n: s.faces_blurred })}</span>}
        {s && s.duplicate_of !== null && (
          <Notice kind="error" role="alert">
            <strong>⚠ {t("tasks.duplicate")}</strong>
            <br />
            <span className="small">{t("tasks.duplicateDetail", { id: s.duplicate_of, d: intFromApi(s.duplicate_distance) ?? "?" })}</span>
          </Notice>
        )}
        {s && s.detector_status === "unavailable" && <span className="muted">{t("tasks.detectorUnavailable")}</span>}
        {s && s.detector_status === "ok" && (
          <span>
            {s.detections && s.detections.length > 0
              ? t("tasks.detected", {
                  list: s.detections.map((d) => `${d.cls.replace(/_/g, " ")} (${d.confidence.toFixed(2)})`).join(", "),
                })
              : t("tasks.nothingDetected")}
          </span>
        )}
      </figcaption>
    </figure>
  );
}

export function PhotoSlot({
  assessmentId,
  taskId,
  spec,
  evidence,
  actor,
  disabled,
}: {
  assessmentId: string;
  taskId: string;
  spec: LabelledItem;
  evidence: EvidenceView[];
  actor: string;
  disabled: boolean;
}) {
  const { t, pick } = useI18n();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [prepared, setPrepared] = useState<PreparedPhoto | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = pick(spec);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setPrepared(await preparePhoto(file));
    } catch (e) {
      setError(t("tasks.photoFailed", { msg: errorText(e) }));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const save = async () => {
    if (!prepared || !consent) return;
    setBusy(true);
    try {
      await addPhoto({ assessmentId, taskId, photoId: spec.id, imageB64: prepared.b64, thumb: prepared.thumb, actor });
      setPrepared(null);
      setConsent(false);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="photo-slot">
      <div className="row between wrap gap-s">
        <strong className="small">📷 {label}</strong>
        <span className="small muted">{t("tasks.photoCount", { n: evidence.length })}</span>
      </div>
      {evidence.length > 0 && (
        <div className="evidence-grid">
          {evidence.map((ev) => (
            <EvidenceCard key={ev.key} ev={ev} slotLabel={label} />
          ))}
        </div>
      )}
      {!disabled && !prepared && (
        <>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept="image/*"
            capture="environment"
            className="visually-hidden-input"
            onChange={(e) => void onFile(e.target.files?.[0])}
            disabled={busy}
          />
          <label htmlFor={inputId} className={`btn btn-block ${busy ? "disabled" : ""}`}>
            {busy ? t("tasks.processing") : t("tasks.takePhoto")}
          </label>
        </>
      )}
      {prepared && (
        <div className="capture stack-s">
          <img src={prepared.thumb} alt={t("tasks.previewAlt")} className="preview" />
          <span className="hint">
            {t("tasks.size", { w: prepared.width, h: prepared.height, kb: Math.round(prepared.bytes / 1024) })}
          </span>
          <Notice kind="info">🔒 {t("tasks.localOnly")}</Notice>
          <label className="check">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>{t("tasks.consent")}</span>
          </label>
          {!consent && <span className="hint">{t("tasks.consentNeeded")}</span>}
          <div className="row gap wrap">
            <button type="button" className="btn btn-primary" disabled={!consent || busy} onClick={() => void save()}>
              {t("tasks.savePhoto")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => { setPrepared(null); setConsent(false); }}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
      {error && <Notice kind="error" role="alert">{error}</Notice>}
    </div>
  );
}
