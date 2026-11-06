// Video pilot: one short clip per part, asked for by the app. The server blurs faces, removes the sound
// and transcribes the clip; the words found are reasons for a suggested level, never a score. Clips are
// large, so they need a connection and are not queued offline like photos.
import { useEffect, useRef, useState } from "react";
import { api, fetchBlob, type ClipPrompt, type GuidedClipOut, type Task } from "../api";
import { tryRefreshAssessment, type AssessmentView } from "../data";
import { useI18n, type Key } from "../i18n";
import { isConnected, useStatus } from "../status";
import { Notice } from "./common";
import { ErrorBox, SpeakButton } from "./ui";

const ASPECTS = ["name", "function", "failure", "test"] as const;

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

function useAuthedVideo(url: string): string | null {
  const [obj, setObj] = useState<string | null>(null);
  useEffect(() => {
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

const MAX_TIMES = 8;

/** Seconds at which the frame check saw something, as buttons that jump the video there. */
function FrameTimes({ label, times, seek }: { label: string; times: number[]; seek: (s: number) => void }) {
  return (
    <>
      <strong>{label}</strong>{" "}
      {times.slice(0, MAX_TIMES).map((s) => (
        <button key={s} type="button" className="chip-link" onClick={() => seek(s)}>
          {mmss(s)}
        </button>
      ))}
      {times.length > MAX_TIMES && <span className="muted"> +{times.length - MAX_TIMES}</span>}
    </>
  );
}

/** A stored clip: the blurred, silent video, what was said for each aspect (click to jump), the meter check. */
function ClipReview({ clip, prompt }: { clip: GuidedClipOut; prompt: ClipPrompt }) {
  const { t } = useI18n();
  const src = useAuthedVideo(clip.video_url);
  const video = useRef<HTMLVideoElement>(null);
  const seek = (s: number) => {
    if (!video.current) return;
    video.current.currentTime = s;
    void video.current.play().catch(() => undefined);
  };
  const aspects = ASPECTS.filter((a) => a in prompt.terms);
  const frames = clip.frames ?? [];
  const seenAt = frames.filter((f) => f.part !== null).map((f) => f.t);
  const heldAt = frames.filter((f) => f.hand_on_part).map((f) => f.t);
  return (
    <div className="clip-review stack-s">
      {src ? <video ref={video} src={src} controls playsInline muted className="clip-video" /> : <p className="muted small">{t("common.loading")}</p>}
      <ul className="plain small stack-s">
        {aspects.map((a) => {
          const hits = clip.found[a] ?? [];
          return (
            <li key={a}>
              <strong>{t(`clips.aspect.${a}` as Key)}:</strong>{" "}
              {hits.length ? (
                hits.map(([word, s], i) => (
                  <button key={i} type="button" className="chip-link" onClick={() => seek(s)}>
                    “{word}” {mmss(s)}
                  </button>
                ))
              ) : (
                <span className="warn-text">{t("clips.notSaid")}</span>
              )}
            </li>
          );
        })}
        {clip.part_seen === null ? (
          <li className="muted">{t("clips.framesNotChecked")}</li>
        ) : (
          <>
            <li className={clip.part_seen ? "" : "warn-text"}>
              {clip.part_seen ? <FrameTimes label={t("clips.partSeenAt")} times={seenAt} seek={seek} /> : t("clips.partNotSeen")}
            </li>
            {clip.part_seen &&
              (clip.hand_on_part === null ? (
                <li className="muted">{t("clips.handNotChecked")}</li>
              ) : (
                <li>
                  {clip.hand_on_part ? <FrameTimes label={t("clips.handOnAt")} times={heldAt} seek={seek} /> : t("clips.handNotOn")}
                </li>
              ))}
            <li className="muted">{t("clips.frameNote")}</li>
          </>
        )}
        {prompt.meter && clip.meter_in_range !== null && (
          <li className={clip.meter_in_range ? "" : "warn-text"}>
            {t(clip.meter_in_range ? "clips.meterIn" : "clips.meterOut", {
              r: clip.meter_value ?? "?",
              p: clip.printed_value ?? "?",
              u: prompt.meter.unit,
            })}
          </li>
        )}
      </ul>
      <details className="sub">
        <summary>{t("clips.transcript")}</summary>
        {clip.transcript.unavailable ? (
          <p className="muted small">{t("clips.noSpeech")}</p>
        ) : (
          <p className="small">{clip.transcript.text || "—"}</p>
        )}
      </details>
    </div>
  );
}

type Rec = { state: "idle" } | { state: "live"; stream: MediaStream; rec: MediaRecorder; started: number } | { state: "done"; blob: Blob; url: string; seconds: number };

function ClipRecorder({ view, task, prompt }: { view: AssessmentView; task: Task; prompt: ClipPrompt }) {
  const { t, lang, pick, pickL } = useI18n();
  const online = isConnected(useStatus());
  const [rec, setRec] = useState<Rec>({ state: "idle" });
  const [consent, setConsent] = useState(false);
  const [reading, setReading] = useState("");
  const [printed, setPrinted] = useState("");
  const [tolerance, setTolerance] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const live = useRef<HTMLVideoElement>(null);
  const clips = view.clips.filter((c) => c.task_id === task.task_id && c.clip_id === prompt.id);
  const latest = clips.length ? clips[clips.length - 1] : undefined;
  const [promptText, promptLang] = pickL(prompt.prompt);

  useEffect(() => {
    if (rec.state === "live" && live.current) live.current.srcObject = rec.stream;
    return () => {
      if (rec.state === "done") URL.revokeObjectURL(rec.url);
    };
  }, [rec]);

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: true });
      const r = new MediaRecorder(stream);
      const parts: Blob[] = [];
      const started = performance.now();
      r.ondataavailable = (e) => e.data.size && parts.push(e.data);
      r.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(parts, { type: r.mimeType || "video/webm" });
        setRec({ state: "done", blob, url: URL.createObjectURL(blob), seconds: Math.round((performance.now() - started) / 1000) });
      };
      r.start();
      setRec({ state: "live", stream, rec: r, started });
    } catch (e) {
      setError(new Error(t("clips.camera", { error: e instanceof Error ? e.message : String(e) })));
    }
  };

  const num = (v: string) => (v.trim() === "" ? undefined : Number(v.replace(",", ".")));
  const upload = async () => {
    if (rec.state !== "done") return;
    setBusy(true);
    setError(null);
    try {
      await api.addClip(view.id, {
        taskId: task.task_id,
        clipId: prompt.id,
        video: rec.blob,
        language: lang,
        reading: num(reading),
        printed: num(printed),
        tolerancePct: num(tolerance),
      });
      setRec({ state: "idle" });
      await tryRefreshAssessment(view.id, { prescores: true });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card stack-s clip-card">
      <div className="row wrap gap-s between">
        <strong>{pick(prompt.part)}</strong>
        <span className="small muted">{clips.length ? t("clips.count", { n: clips.length }) : t("clips.none")}</span>
      </div>
      <p lang={promptLang}>{promptText}</p>
      <SpeakButton small text={promptText} lang={promptLang} />
      {latest && <ClipReview clip={latest} prompt={prompt} />}
      {!view.signedOff &&
        (!online ? (
          <Notice kind="info">{t("clips.needOnline")}</Notice>
        ) : rec.state === "live" ? (
          <div className="stack-s">
            <video ref={live} autoPlay muted playsInline className="clip-video" />
            <button type="button" className="btn btn-danger btn-block" onClick={() => rec.rec.stop()}>
              {t("clips.stop")}
            </button>
          </div>
        ) : rec.state === "done" ? (
          <div className="stack-s">
            <video src={rec.url} controls playsInline className="clip-video" />
            <p className="small muted">{t("clips.recorded", { n: rec.seconds })}</p>
            {prompt.meter && (
              <div className="two-col">
                <label className="field">
                  <span className="label">{t("clips.reading", { u: prompt.meter.unit })}</span>
                  <input type="text" inputMode="decimal" value={reading} onChange={(e) => setReading(e.target.value)} />
                </label>
                <label className="field">
                  <span className="label">{t("clips.printed", { u: prompt.meter.unit })}</span>
                  <input type="text" inputMode="decimal" value={printed} onChange={(e) => setPrinted(e.target.value)} />
                </label>
                <label className="field">
                  <span className="label">{t("clips.tolerance")}</span>
                  <input type="text" inputMode="decimal" value={tolerance} onChange={(e) => setTolerance(e.target.value)} />
                </label>
              </div>
            )}
            <label className="check">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>{t("clips.consent")}</span>
            </label>
            <div className="row wrap gap">
              <button type="button" className="btn btn-primary" disabled={!consent || busy} onClick={() => void upload()}>
                {busy ? t("clips.uploading") : t("clips.upload")}
              </button>
              <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setRec({ state: "idle" })}>
                {t("clips.discard")}
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="btn btn-block" onClick={() => void start()}>
            {latest ? t("clips.recordAgain") : t("clips.record")}
          </button>
        ))}
      <ErrorBox error={error} />
    </section>
  );
}

export function GuidedClips({ task, view }: { task: Task; view: AssessmentView }) {
  const { t } = useI18n();
  if (!task.clips?.length) return null;
  return (
    <div className="stack-s">
      <h3>{t("clips.title")}</h3>
      <p className="hint">{t("clips.intro")}</p>
      {task.clips.map((p) => (
        <ClipRecorder key={p.id} view={view} task={task} prompt={p} />
      ))}
    </div>
  );
}
