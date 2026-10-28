import { useEffect, useRef, useState, type FormEvent } from "react";
import { submitRating } from "../actions";
import { api, apiUrl, errorText, type Condition, type StudyItem } from "../api";
import { ErrorText, Notice, SampleBadge } from "../components/common";
import { useLive } from "../data";
import { db, type StudyProgress } from "../db";
import { useI18n } from "../i18n";
import { useSettings } from "../settings";
import { isConnected, useStatus } from "../status";
import { flushRatings } from "../sync";
import { nowIso } from "../util";

const LEVELS = [0, 1, 2, 3];
const progressKey = (r: string, c: Condition, s: number, sample: boolean) => `${r}|${c}|${s}|${sample ? 1 : 0}`;

function RatingQueueInfo() {
  const { t } = useI18n();
  const rows = useLive(() => db.ratings.toArray(), []);
  if (!rows || rows.length === 0) return null;
  const failed = rows.filter((r) => r.error);
  const waiting = rows.length - failed.length;
  return (
    <div className="stack-s">
      {waiting > 0 && <Notice kind="info">{t("rater.pendingUpload", { n: waiting })}</Notice>}
      {failed.length > 0 && (
        <Notice kind="error">
          {t("rater.failed", { n: failed.length, msg: failed[0].error ?? "" })}{" "}
          <button type="button" className="btn btn-small" onClick={() => void db.ratings.bulkDelete(failed.map((f) => f.id!))}>
            {t("rater.discardFailed")}
          </button>
        </Notice>
      )}
    </div>
  );
}

function ItemView({ prog, onRated }: { prog: StudyProgress; onRated: (level: number, seconds: number) => Promise<void> }) {
  const { t, pick } = useI18n();
  const item: StudyItem = prog.items[prog.index];
  const shownAt = useRef(performance.now());
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    shownAt.current = performance.now();
    setBusy(false);
  }, [prog.index]);
  const assisted = prog.condition === "assisted";
  const n = prog.items.length;

  const rate = async (level: number) => {
    if (busy) return;
    setBusy(true);
    const seconds = Math.round(((performance.now() - shownAt.current) / 1000) * 10) / 10;
    await onRated(level, seconds);
  };

  return (
    <div className="stack">
      <div>
        <div className="row between small">
          <span>{t("rater.progress", { i: prog.index + 1, n })}</span>
          <SampleBadge show={item.is_sample} />
        </div>
        <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={n} aria-valuenow={prog.index}>
          <div className="bar-fill tone-brand" style={{ width: `${(prog.index / n) * 100}%` }} />
        </div>
        <p className="hint">{t("rater.noBack")}</p>
      </div>
      <section className="card stack-s">
        <img className="study-img" src={apiUrl(item.image_url)} alt={t("rater.imageAlt")} />
        <p className="small muted">{pick(item.task_title)}</p>
        <p>
          <span className="small muted">{t("rater.criterion")}: </span>
          <strong>{pick(item.criterion)}</strong>
        </p>
      </section>
      {assisted && item.prescore && (
        <section className="card stack-s">
          <h3>{t("rater.toolPrescore")}</h3>
          <p>
            {item.prescore.suggested_level === null
              ? t("rater.noSuggestion")
              : `${t("score.suggested")}: ${item.prescore.suggested_level} – ${pick(item.level_names[String(item.prescore.suggested_level)])}`}
          </p>
          <ul className="reasons small" lang="en">
            {item.prescore.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </section>
      )}
      <fieldset className="stack-s">
        <legend className="label">{t("rater.chooseLevel")}</legend>
        {LEVELS.map((l) => (
          <button key={l} type="button" className="lvl lvl-wide" disabled={busy} onClick={() => void rate(l)}>
            <span className="lvl-n">{l}</span>
            <span className="lvl-name">
              {pick(item.level_names[String(l)])}
              {assisted && item.anchors && (
                <span className="small block anchor" lang="en">
                  {item.anchors[String(l)]}
                </span>
              )}
            </span>
          </button>
        ))}
      </fieldset>
    </div>
  );
}

export function Rater() {
  const { t } = useI18n();
  const { actor } = useSettings();
  const connected = isConnected(useStatus());
  const [raterId, setRaterId] = useState(actor.trim());
  const [condition, setCondition] = useState<Condition>("unassisted");
  const [session, setSession] = useState(1);
  const [includeSample, setIncludeSample] = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const formKey = raterId.trim() ? progressKey(raterId.trim(), condition, session, includeSample) : null;
  const saved = useLive(async () => (formKey ? (await db.studyProgress.get(formKey)) ?? null : null), [formKey]);
  const active = useLive(async () => (activeKey ? (await db.studyProgress.get(activeKey)) ?? null : null), [activeKey]);

  const start = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (!formKey) {
      setError(t("rater.raterIdRequired"));
      return;
    }
    if (saved && saved.done) {
      setInfo(t("rater.alreadyDone"));
      return;
    }
    if (saved) {
      setActiveKey(formKey);
      return;
    }
    if (!connected) {
      setError(t("rater.needOnline"));
      return;
    }
    setBusy(true);
    try {
      const items = await api.studyItems({ rater_id: raterId.trim(), condition, include_sample: includeSample });
      if (items.length === 0) {
        setInfo(t("rater.noItems"));
        return;
      }
      // Warm the image cache so the session can continue if the connection drops.
      items.forEach((it) => void fetch(apiUrl(it.image_url)).catch(() => undefined));
      await db.studyProgress.put({
        key: formKey,
        rater_id: raterId.trim(),
        condition,
        session,
        include_sample: includeSample,
        items,
        index: 0,
        rated: 0,
        started_at: nowIso(),
        done: false,
      });
      setActiveKey(formKey);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const onRated = async (level: number, seconds: number) => {
    if (!active) return;
    const item = active.items[active.index];
    await submitRating({
      rater_id: active.rater_id,
      item_id: item.item_id,
      condition: active.condition,
      session: active.session,
      position: item.position,
      level,
      seconds,
    });
    const next = active.index + 1;
    await db.studyProgress.update(active.key, { index: next, rated: active.rated + 1, done: next >= active.items.length });
  };

  if (activeKey && active) {
    if (active.done) {
      return (
        <div className="stack">
          <section className="card stack-s center">
            <h1>🙏 {t("rater.thanks")}</h1>
            <p>{t("rater.thanksBody", { n: active.rated })}</p>
          </section>
          <RatingQueueInfo />
          <button
            type="button"
            className="btn btn-block"
            onClick={() => {
              setActiveKey(null);
              void flushRatings();
            }}
          >
            {t("rater.backToStart")}
          </button>
        </div>
      );
    }
    return (
      <div className="stack">
        <RatingQueueInfo />
        <ItemView prog={active} onRated={onRated} />
      </div>
    );
  }

  return (
    <form className="stack" onSubmit={(e) => void start(e)}>
      <h1>{t("rater.title")}</h1>
      <p>{t("rater.intro")}</p>
      <Notice kind="warn">📅 {t("rater.weekApart")}</Notice>
      <section className="card stack-s">
        <label className="field">
          <span className="label">{t("rater.raterId")}</span>
          <input type="text" value={raterId} onChange={(e) => setRaterId(e.target.value)} autoComplete="off" spellCheck={false} />
        </label>
        <fieldset className="stack-s">
          <legend className="label">{t("rater.condition")}</legend>
          {(["unassisted", "assisted"] as const).map((c) => (
            <label key={c} className={`radio-card ${condition === c ? "on" : ""}`}>
              <input type="radio" name="condition" checked={condition === c} onChange={() => setCondition(c)} />
              <span>{t(c === "assisted" ? "rater.assisted" : "rater.unassisted")}</span>
            </label>
          ))}
        </fieldset>
        <label className="field">
          <span className="label">{t("rater.session")}</span>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            value={session}
            onChange={(e) => setSession(Math.max(1, Math.floor(Number(e.target.value) || 1)))}
          />
        </label>
        <label className="check">
          <input type="checkbox" checked={includeSample} onChange={(e) => setIncludeSample(e.target.checked)} />
          <span>{t("rater.includeSample")}</span>
        </label>
      </section>
      {info && <Notice kind="info">{info}</Notice>}
      <ErrorText error={error} />
      <RatingQueueInfo />
      <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
        {saved && !saved.done ? t("rater.resume", { i: saved.index + 1, n: saved.items.length }) : t("rater.start")}
      </button>
    </form>
  );
}
