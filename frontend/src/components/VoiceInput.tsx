import { useEffect, useRef, useState } from "react";
import { api, errorText, type Lang } from "../api";
import { useI18n } from "../i18n";
import { isConnected, useStatus } from "../status";
import { ErrorText, Notice } from "./common";

const MAX_MS = 3 * 60 * 1000;

/** Recording needs MediaRecorder and a secure context (https or localhost). */
function canRecord(): boolean {
  return typeof window !== "undefined" && "MediaRecorder" in window && !!navigator.mediaDevices?.getUserMedia;
}

/**
 * Records the worker speaking and returns a draft transcript (faster-whisper on the server).
 * The audio is sent once for transcription and never stored; the facilitator must check the text.
 */
export function VoiceInput({ language, onText }: { language: Lang; onText: (text: string) => void }) {
  const { t } = useI18n();
  const status = useStatus();
  const [installed, setInstalled] = useState<boolean | null>(null);
  const [state, setState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setInstalled(!!h.speech?.available))
      .catch(() => alive && setInstalled(null));
    return () => {
      alive = false;
      window.clearTimeout(timer.current);
      rec.current?.stream.getTracks().forEach((tr) => tr.stop());
    };
  }, []);

  const start = async () => {
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError(t("voice.micDenied"));
      return;
    }
    const r = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    r.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data);
    };
    r.onstop = async () => {
      stream.getTracks().forEach((tr) => tr.stop());
      window.clearTimeout(timer.current);
      setState("transcribing");
      try {
        const res = await api.transcribe(new Blob(chunks, { type: r.mimeType || "audio/webm" }), language);
        if (res.text.trim()) onText(res.text.trim());
        else setError(t("voice.empty"));
      } catch (e) {
        setError(errorText(e));
      }
      setState("idle");
    };
    rec.current = r;
    r.start();
    setState("recording");
    timer.current = window.setTimeout(() => r.state === "recording" && r.stop(), MAX_MS);
  };

  const stop = () => {
    if (rec.current?.state === "recording") rec.current.stop();
  };

  const blocked = !canRecord()
    ? t("voice.unsupported")
    : !isConnected(status)
      ? t("voice.offline")
      : installed === false
        ? t("voice.notInstalled")
        : null;

  return (
    <div className="stack">
      {state === "recording" ? (
        <button type="button" className="btn btn-danger" onClick={stop}>
          ⏹ {t("voice.stop")}
        </button>
      ) : (
        <button
          type="button"
          className="btn"
          onClick={() => void start()}
          disabled={!!blocked || state === "transcribing"}
          aria-describedby="voice-note"
        >
          🎤 {state === "transcribing" ? t("voice.transcribing") : t("voice.record")}
        </button>
      )}
      {state === "recording" && (
        <Notice kind="info" role="status">
          {t("voice.recording")}
        </Notice>
      )}
      <span id="voice-note" className="hint">
        {blocked ?? t("voice.note")}
      </span>
      <ErrorText error={error} />
    </div>
  );
}
