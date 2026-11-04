import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText, type Gap, type Outcome, type Rubrics } from "../api";
import { Bar, CriticalBadge, Loading, Notice } from "../components/common";
import { refreshAssessment, refreshAssessmentList, tryRefreshAssessment, useRubrics, type AssessmentView } from "../data";
import { useI18n, type Key } from "../i18n";
import { actorName, useSettings } from "../settings";
import { isConnected, useStatus } from "../status";
import { fmtTime, pct } from "../util";
import { useAssessmentCtx } from "./AssessmentLayout";

function GapItem({ g, rubrics }: { g: Gap; rubrics: Rubrics | null | undefined }) {
  const { pick } = useI18n();
  const task = rubrics?.tasks.find((x) => x.task_id === g.task_id);
  const cr = task?.criteria.find((c) => c.id === g.criterion_id);
  return (
    <li className="gap-item">
      <div className="row wrap gap-s">
        {g.critical && <CriticalBadge />}
        <code className="small">{g.nos}</code>
        <span className="small muted">{task ? pick(task.title) : g.task_id}</span>
      </div>
      <div>
        {cr ? pick(cr.text) : g.text} — <strong>{g.level}</strong>
        {rubrics && ` (${pick(rubrics.levels[String(g.level)])})`}
      </div>
    </li>
  );
}

function SignedOff({ view }: { view: AssessmentView }) {
  const { t } = useI18n();
  const s = view.signoff!;
  return (
    <section className="card signed">
      <h3>✔ {t("profile.signedOff")}</h3>
      <p>{t("profile.signedBy", { name: s.assessor })}</p>
      <p>
        <strong>{t("profile.assessorOutcome", { outcome: t(`profile.outcome.${s.assessor_outcome}` as Key) })}</strong>
      </p>
      <p className="small">
        {t("profile.toolRec", {
          rec:
            s.tool_recommendation === "incomplete"
              ? t("profile.rec.incomplete")
              : t(`profile.outcome.${s.tool_recommendation}` as Key),
        })}{" "}
        {s.agrees_with_tool ? t("profile.agreed") : t("profile.disagreed")}
      </p>
      {s.overall !== null && <p className="small">{t("profile.overallAtSignoff", { p: pct(s.overall) })}</p>}
      {s.comment && <blockquote className="quote">{s.comment}</blockquote>}
      <p className="small muted">🔒 {t("profile.frozen")}</p>
    </section>
  );
}

function SignoffForm({ view, blocked }: { view: AssessmentView; blocked: string | null }) {
  const { t } = useI18n();
  const settings = useSettings();
  const [agrees, setAgrees] = useState(true);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const name = actorName(settings);
  const valid = agrees || (outcome !== null && comment.trim().length >= 5);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.signoff(view.id, { assessor: name, agrees, outcome: agrees ? null : outcome, comment: comment.trim() });
      await refreshAssessment(view.id, { profile: true });
      await refreshAssessmentList().catch(() => undefined);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card stack-s">
      <h3>{t("profile.signoff")}</h3>
      <p className="hint">📶 {t("profile.signoffOnline")}</p>
      {blocked && <Notice kind="warn">{blocked}</Notice>}
      <fieldset className="stack-s" disabled={!!blocked || busy}>
        <legend className="sr-only">{t("profile.signoff")}</legend>
        <label className={`radio-card ${agrees ? "on" : ""}`}>
          <input type="radio" name="agree" checked={agrees} onChange={() => setAgrees(true)} />
          <span>{t("profile.agree")}</span>
        </label>
        <label className={`radio-card ${!agrees ? "on" : ""}`}>
          <input type="radio" name="agree" checked={!agrees} onChange={() => setAgrees(false)} />
          <span>{t("profile.disagree")}</span>
        </label>
        {!agrees && (
          <label className="field">
            <span className="label">{t("profile.outcome")}</span>
            <select value={outcome ?? ""} onChange={(e) => setOutcome((e.target.value || null) as Outcome | null)}>
              <option value="">—</option>
              <option value="not_yet_competent">{t("profile.outcome.not_yet_competent")}</option>
              <option value="recommend_for_certification">{t("profile.outcome.recommend_for_certification")}</option>
            </select>
          </label>
        )}
        <label className="field">
          <span className="label">{agrees ? t("profile.commentOptional") : t("profile.comment")}</span>
          <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
          {!agrees && <span className="hint">{t("profile.commentRequired")}</span>}
        </label>
        <p className="small muted">{t("profile.signingAs", { name })}</p>
        <button type="button" className="btn btn-primary" disabled={!valid || !!blocked || busy} onClick={() => void submit()}>
          {busy ? t("profile.submitting") : t("profile.submit")}
        </button>
      </fieldset>
      {error && <Notice kind="error" role="alert">{error}</Notice>}
    </section>
  );
}

export function ProfileScreen() {
  const { t, lang } = useI18n();
  const { view } = useAssessmentCtx();
  const rubrics = useRubrics();
  const connected = isConnected(useStatus());
  const snap = view.snapshot;
  const p = snap?.profile;

  useEffect(() => {
    if (connected && view.onServer) void tryRefreshAssessment(view.id, { profile: true });
  }, [connected, view.id, view.onServer, view.decisionsPending]);

  if (!view.onServer && !p) return <Notice kind="info">{t("profile.missing")}</Notice>;
  if (!p) return connected ? <Loading /> : <Notice kind="warn">{t("profile.missing")}</Notice>;

  const pending = view.pendingOps.length;
  const blocked = !connected
    ? t("common.needsConnection")
    : pending > 0
      ? t("profile.signoffNeedsSync")
      : view.confirmed_nqr_id === null
        ? t("profile.signoffNeedsPack")
        : p.unscored.length > 0
          ? t("profile.signoffNeedsAll")
          : null;
  const tone = p.overall === null ? "brand" : p.overall + 1e-9 >= p.pass_mark ? "ok" : "warn";

  return (
    <div className="stack">
      <h2>{t("profile.title")}</h2>
      {snap?.profile_at && <p className="hint">{t("common.cachedAt", { time: fmtTime(snap.profile_at, lang) })}</p>}
      {pending > 0 && <Notice kind="warn">{t("profile.stale", { n: pending })}</Notice>}

      <section className="card stack-s">
        <h3>{t("profile.overall")}</h3>
        {p.overall === null ? (
          <p className="muted">{t("profile.noneScored")}</p>
        ) : (
          <p className="big">{pct(p.overall)}</p>
        )}
        <Bar value={p.overall} marker={p.pass_mark} tone={tone} label={`${t("profile.overall")} ${pct(p.overall)}`} />
        <p className="small">{t("profile.passMark", { p: pct(p.pass_mark) })}</p>
        {p.nos_pass_mark != null && <p className="small">{t("profile.nosPassMark", { p: pct(p.nos_pass_mark) })}</p>}
        {p.unscored.length > 0 && (
          <p className="row wrap gap-s">
            <span className="warn-text">{t("profile.unscored", { n: p.unscored.length })}</span>
            <Link to="../score" relative="path" className="btn btn-small">
              {t("profile.goScore")}
            </Link>
          </p>
        )}
      </section>

      <section className="card stack-s">
        <h3>{t("profile.nos")}</h3>
        {p.nos.length === 0 && <p className="muted">{t("profile.noneScored")}</p>}
        <ul className="plain stack-s">
          {p.nos.map((n) => (
            <li key={n.nos}>
              <div className="row between small">
                <code>{n.nos}</code>
                <strong>{pct(n.score)}</strong>
              </div>
              <Bar value={n.score} marker={p.nos_pass_mark ?? p.pass_mark} label={`${n.nos} ${pct(n.score)}`} tone={n.score + 1e-9 >= (p.nos_pass_mark ?? p.pass_mark) ? "ok" : "warn"} />
              <div className="small muted">{t("profile.nosLine", { n: n.criteria, b: n.below_competent })}</div>
            </li>
          ))}
        </ul>
      </section>

      <section className={`card stack-s ${p.critical_failures.length ? "card-bad" : ""}`}>
        <h3>{t("profile.critical")}</h3>
        <p className="small">{t("profile.criticalExplain")}</p>
        {p.critical_failures.length === 0 ? (
          <p className="muted">{t("profile.noCritical")}</p>
        ) : (
          <ul className="plain stack-s">
            {p.critical_failures.map((g) => (
              <GapItem key={`${g.task_id}.${g.criterion_id}`} g={g} rubrics={rubrics} />
            ))}
          </ul>
        )}
      </section>

      <section className="card stack-s">
        <h3>{t("profile.gaps")}</h3>
        {p.gaps.length === 0 ? (
          <p className="muted">{t("profile.noGaps")}</p>
        ) : (
          <ul className="plain stack-s">
            {p.gaps.map((g) => (
              <GapItem key={`${g.task_id}.${g.criterion_id}`} g={g} rubrics={rubrics} />
            ))}
          </ul>
        )}
      </section>

      <section className="card stack-s rec">
        <h3>{t("profile.recTitle")}</h3>
        <p>
          <strong>{t(`profile.rec.${p.recommendation}` as Key)}</strong>
        </p>
        <p className="small">
          {t("profile.toolExplain")}: <span lang="en">{p.explanation}</span>
        </p>
      </section>

      {view.signedOff && view.signoff ? <SignedOff view={view} /> : <SignoffForm view={view} blocked={blocked} />}
    </div>
  );
}
