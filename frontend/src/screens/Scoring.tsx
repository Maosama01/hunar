import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { decide } from "../actions";
import { errorText, type Criterion, type PreScore, type Rubrics, type Task } from "../api";
import { Bar, CriticalBadge, Loading, Notice, PendingBadge, PresenceNote } from "../components/common";
import { Icon } from "../components/Icon";
import { PackConfirm } from "../components/PackConfirm";
import { decisionKey, tryRefreshAssessment, useRubrics, type AssessmentView, type DecisionView } from "../data";
import { useI18n, type Key } from "../i18n";
import { actorName, useSettings } from "../settings";
import { isConnected, useStatus } from "../status";
import { fmtTime } from "../util";
import { useAssessmentCtx } from "./AssessmentLayout";

const LEVELS = [0, 1, 2, 3];

function DecisionLine({ d, rubrics }: { d: DecisionView | undefined; rubrics: Rubrics }) {
  const { t, pick, lang } = useI18n();
  if (!d) return <p className="muted small">{t("score.none")}</p>;
  return (
    <div className="decision small">
      <div className="row wrap gap-s">
        <strong>
          {d.level === null
            ? t("score.decisionPendingAccept")
            : t("score.decisionLevel", { level: d.level, name: pick(rubrics.levels[String(d.level)]) })}
        </strong>
        {d.pending && <PendingBadge />}
      </div>
      <div className="muted">
        {t("score.by", { action: t(`score.action.${d.action}` as Key), who: d.assessor })} · {fmtTime(d.created_at, lang)}
      </div>
      {d.reason && <div>{t("score.reasonGiven", { reason: d.reason })}</div>}
    </div>
  );
}

/** The four levels at a glance: dashed = suggested by the tool, filled = decided by the assessor.
 * On a safety criterion the two lowest levels carry a red underline (they block a positive result). */
function LevelStrip({ suggested, decided, critical }: { suggested: number | null; decided: number | null; critical: boolean }) {
  const { t } = useI18n();
  const none = t("score.levelNone");
  return (
    <div
      className="level-strip"
      role="img"
      aria-label={t("score.levelStripAria", { s: suggested ?? none, d: decided ?? none })}
    >
      {LEVELS.map((l) => (
        <span
          key={l}
          aria-hidden="true"
          className={`${suggested === l ? "is-suggested" : ""} ${decided === l ? "is-decided" : ""} ${critical && l < 2 ? "is-critical-floor" : ""}`}
        >
          {l}
        </span>
      ))}
    </div>
  );
}

function CriterionCard({
  task,
  cr,
  pre,
  view,
  rubrics,
  acceptBlocked,
}: {
  task: Task;
  cr: Criterion;
  pre: PreScore | undefined;
  view: AssessmentView;
  rubrics: Rubrics;
  acceptBlocked: boolean;
}) {
  const { t, pick } = useI18n();
  const settings = useSettings();
  const [overriding, setOverriding] = useState(false);
  const [level, setLevel] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const d = view.decisions[decisionKey(task.task_id, cr.id)];
  const suggested = pre?.suggested_level ?? null;
  const frozen = view.signedOff;
  const reasonOk = reason.trim().length >= 5;

  const run = async (action: "accept" | "override") => {
    setError(null);
    try {
      await decide({
        assessmentId: view.id,
        taskId: task.task_id,
        criterionId: cr.id,
        action,
        level: action === "override" ? level : null,
        reason: action === "override" ? reason.trim() : null,
        assessor: actorName(settings),
        shownLevel: action === "override" ? level : suggested,
      });
      setOverriding(false);
      setReason("");
      setLevel(null);
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <article className={`card criterion ${cr.critical ? "is-critical" : ""} ${pre?.conflict ? "is-conflict" : ""}`}>
      <header className="stack-s">
        <div className="row wrap gap-s">
          {cr.critical && <CriticalBadge />}
          <code className="small">{cr.nos}</code>
          <span className="small muted">{t("score.weight", { w: cr.weight })}</span>
        </div>
        <h4>{pick(cr.text)}</h4>
        <LevelStrip suggested={suggested} decided={d?.level ?? null} critical={cr.critical} />
        {cr.critical && <p className="small warn-text">{t("score.criticalNote")}</p>}
      </header>

      <div className="suggestion">
        {pre && suggested !== null ? (
          <p>
            {t("score.suggested")}:{" "}
            <strong>
              {suggested} – {pick(rubrics.levels[String(suggested)])}
            </strong>{" "}
            <span className={`conf conf-${pre.confidence}`}>
              {t("score.confidence", { c: t(`score.conf.${pre.confidence}` as Key) })}
            </span>
          </p>
        ) : (
          <p className="muted">{t("score.noSuggestion")}</p>
        )}
        {pre?.conflict && (
          <Notice kind="error" role="alert">
            ⚠ {t("score.conflict")}
          </Notice>
        )}
        {pre && pre.reasons.length > 0 && (
          <>
            <p className="small label-inline">{t("score.reasons")}:</p>
            <ul className="reasons small" lang="en">
              {pre.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      <details className="sub">
        <summary>{t("score.levels")}</summary>
        <ol className="levels" start={0}>
          {LEVELS.map((l) => (
            <li key={l} className={`${suggested === l ? "is-suggested" : ""} ${d?.level === l ? "is-decided" : ""}`}>
              <strong>
                {l} – {pick(rubrics.levels[String(l)])}
              </strong>
              <span lang="en"> {cr.levels[String(l)]}</span>
            </li>
          ))}
        </ol>
        <p className="hint">{t("score.descriptorsEnglish")}</p>
      </details>

      <div className="latest">
        <p className="small label-inline">{t("score.latest")}:</p>
        <DecisionLine d={d} rubrics={rubrics} />
      </div>

      {!frozen && (
        <div className="decide-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={suggested === null || acceptBlocked}
            onClick={() => void run("accept")}
          >
            {t("score.accept")}
          </button>
          <button
            type="button"
            className="btn"
            aria-expanded={overriding}
            onClick={() => setOverriding((o) => !o)}
          >
            {t("score.override")}
          </button>
        </div>
      )}

      {overriding && !frozen && (
        <div className="override stack-s">
          <fieldset>
            <legend className="label">{t("score.overrideLevel")}</legend>
            <div className="level-pick">
              {LEVELS.map((l) => (
                <button
                  key={l}
                  type="button"
                  className={`lvl ${level === l ? "on" : ""}`}
                  aria-pressed={level === l}
                  onClick={() => setLevel(l)}
                >
                  <span className="lvl-n">{l}</span>
                  <span className="lvl-name">{pick(rubrics.levels[String(l)])}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <label className="field">
            <span className="label">{t("score.overrideReason")}</span>
            <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={reason.length > 0 && !reasonOk} />
            <span className="hint">{reason.trim().length} / 5</span>
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={level === null || !reasonOk}
            onClick={() => void run("override")}
          >
            {t("score.saveOverride")}
          </button>
        </div>
      )}
      {error && <Notice kind="error">{error}</Notice>}
    </article>
  );
}

export function Scoring() {
  const { t, lang } = useI18n();
  const { view } = useAssessmentCtx();
  const rubrics = useRubrics();
  const connected = isConnected(useStatus());
  const snap = view.snapshot;

  useEffect(() => {
    if (connected && view.onServer) void tryRefreshAssessment(view.id, { prescores: true });
  }, [connected, view.id, view.onServer, view.prescoreAffectingPending]);

  if (rubrics === undefined) return <Loading />;
  if (rubrics === null) return <Notice kind="warn">{t("common.needsConnection")}</Notice>;

  const prescores = snap?.prescores;
  const preByKey = new Map((prescores ?? []).map((p) => [decisionKey(p.task_id, p.criterion_id), p]));
  const total = rubrics.tasks.reduce((n, task) => n + task.criteria.length, 0);
  const decided = Object.keys(view.decisions).length;
  const stale = view.prescoreAffectingPending > 0;
  const acceptBlocked = stale || !prescores;

  return (
    <div className="stack">
      <h2>{t("score.title")}</h2>
      <PackConfirm view={view} />

      <section className="stack">
        <h3>{t("score.criteriaStep")}</h3>
        {view.confirmed_nqr_id === null ? (
          <Notice kind="info">{t("score.confirmFirst")}</Notice>
        ) : (
          <>
            <div>
              <div className="progress-head">
                <strong>{t("score.progress", { d: decided, t: total })}</strong>
                <span className="small muted">{Math.round((decided / Math.max(1, total)) * 100)}%</span>
              </div>
              <Bar value={total ? decided / total : 0} label={t("score.progress", { d: decided, t: total })} tone={decided === total ? "ok" : "brand"} />
            </div>
            {prescores && snap?.prescores_at && (
              <p className="hint">{t("score.prescoresAt", { time: fmtTime(snap.prescores_at, lang) })}</p>
            )}
            {!prescores && <Notice kind="warn">{t("score.prescoresMissing")}</Notice>}
            {stale && <Notice kind="warn">{t("score.prescoresStale", { n: view.prescoreAffectingPending })}</Notice>}
            {!connected && prescores && <Notice kind="info">{t("common.offlineCopy")}</Notice>}
            <PresenceNote />
            <TaskStepper view={view} rubrics={rubrics} preByKey={preByKey} acceptBlocked={acceptBlocked} />
          </>
        )}
      </section>
    </div>
  );
}

/** One practical task at a time. The rail shows every task with its progress; the assessor moves
 * through them in order or jumps to any one. Opens on the first task that still has undecided
 * criteria, and ends on the profile (sign off) once the last task is done. */
function TaskStepper({
  view,
  rubrics,
  preByKey,
  acceptBlocked,
}: {
  view: AssessmentView;
  rubrics: Rubrics;
  preByKey: Map<string, PreScore>;
  acceptBlocked: boolean;
}) {
  const { t, pick } = useI18n();
  const tasks = rubrics.tasks;
  const counts = useMemo(
    () =>
      tasks.map((task) => ({
        done: task.criteria.filter((cr) => view.decisions[decisionKey(task.task_id, cr.id)] !== undefined).length,
        total: task.criteria.length,
      })),
    [tasks, view.decisions],
  );
  const firstOpen = Math.max(0, counts.findIndex((c) => c.done < c.total));
  const [idx, setIdx] = useState(firstOpen);
  const i = Math.min(idx, tasks.length - 1);
  const task = tasks[i];
  if (!task) return null;
  const go = (n: number) => {
    setIdx(n);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const last = i === tasks.length - 1;

  return (
    <>
      <div className="task-rail" role="tablist" aria-label={t("score.tasksAria")}>
        {tasks.map((tk, n) => {
          const c = counts[n];
          const complete = c.total > 0 && c.done === c.total;
          return (
            <button
              key={tk.task_id}
              type="button"
              role="tab"
              aria-selected={n === i}
              className={`task-pill ${n === i ? "is-active" : ""} ${complete ? "is-done" : ""}`}
              onClick={() => go(n)}
            >
              <span className="task-n" aria-hidden="true">
                {complete ? "✓" : n + 1}
              </span>
              <span className="task-t">{pick(tk.title)}</span>
              <span className="sr-only">{t("score.taskDecided", { d: c.done, t: c.total })}</span>
            </button>
          );
        })}
      </div>

      <section className="card task-head" role="tabpanel" aria-label={pick(task.title)}>
        <div className="grow">
          <span className="task-kicker">{t("score.taskOf", { n: i + 1, t: tasks.length })}</span>
          <h3>{pick(task.title)}</h3>
        </div>
        <span className={`badge ${counts[i].done === counts[i].total ? "badge-signed" : ""}`}>
          {t("score.taskDecided", { d: counts[i].done, t: counts[i].total })}
        </span>
      </section>

      {task.criteria.map((cr) => (
        <CriterionCard
          key={cr.id}
          task={task}
          cr={cr}
          pre={preByKey.get(decisionKey(task.task_id, cr.id))}
          view={view}
          rubrics={rubrics}
          acceptBlocked={acceptBlocked}
        />
      ))}

      <div className="task-nav">
        <button type="button" className="btn" disabled={i === 0} onClick={() => go(i - 1)}>
          <Icon name="chevron" className="flip" size={20} /> {t("score.prevTask")}
        </button>
        {last ? (
          <Link to="../profile" relative="route" className="btn btn-primary">
            {t("score.toProfile")}
          </Link>
        ) : (
          <button type="button" className="btn btn-primary" onClick={() => go(i + 1)}>
            {t("score.nextTask")} <Icon name="chevron" className="flip-rtl" size={20} />
          </button>
        )}
      </div>
    </>
  );
}
