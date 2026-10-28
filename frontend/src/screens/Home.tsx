import { useEffect } from "react";
import { Link } from "react-router-dom";
import { PendingBadge, SampleBadge } from "../components/common";
import { refreshAssessmentList, useAssessmentList } from "../data";
import { useI18n, type Key } from "../i18n";
import { ROLES, useSettings } from "../settings";
import { isConnected, useStatus } from "../status";
import { fmtTime } from "../util";

export function Home() {
  const { t, lang } = useI18n();
  const { role, actor, setRole, setActor } = useSettings();
  const list = useAssessmentList();
  const status = useStatus();
  const connected = isConnected(status);
  const hasActor = actor.trim().length > 0;

  useEffect(() => {
    if (connected) void refreshAssessmentList().catch(() => undefined);
  }, [connected]);

  const defaultTab = role === "assessor" ? "score" : "mapping";

  return (
    <div className="stack">
      <section className="card">
        <h1>{t("app.tagline")}</h1>
        <p>{t("home.intro")}</p>
        <label className="field">
          <span className="label">{t("home.actorLabel")}</span>
          <input
            type="text"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            maxLength={64}
            autoComplete="off"
            aria-describedby="actor-hint"
          />
          <span id="actor-hint" className="hint">
            {t("home.actorHint")}
          </span>
        </label>
      </section>

      <section className="card" aria-labelledby="roles-h">
        <h2 id="roles-h">{t("roles.title")}</h2>
        <div className="role-grid">
          {ROLES.map((r) => (
            <button
              key={r}
              type="button"
              className={`role ${role === r ? "selected" : ""}`}
              aria-pressed={role === r}
              onClick={() => setRole(r)}
            >
              <span className="role-name">{t(`roles.${r}` as Key)}</span>
              <span className="role-desc">{t(`roles.${r}Desc` as Key)}</span>
            </button>
          ))}
        </div>
        {role && !hasActor && <p className="hint warn-text">{t("home.actorNeeded")}</p>}
        {role === "facilitator" && (
          <Link to="/declare" className={`btn btn-primary btn-block ${hasActor ? "" : "disabled"}`} aria-disabled={!hasActor} onClick={(e) => !hasActor && e.preventDefault()}>
            {t("home.newDeclaration")}
          </Link>
        )}
        {role === "assessor" && <p className="hint">{t("home.assessorHint")}</p>}
        {role === "admin" && (
          <Link to="/admin" className="btn btn-primary btn-block">
            {t("home.openAdmin")}
          </Link>
        )}
        {role === "rater" && (
          <Link to="/rater" className="btn btn-primary btn-block">
            {t("home.openRater")}
          </Link>
        )}
      </section>

      {(role === "facilitator" || role === "assessor" || role === null) && (
        <section className="card" aria-labelledby="list-h">
          <div className="row between">
            <h2 id="list-h">{t("home.assessments")}</h2>
            <button
              type="button"
              className="btn btn-small btn-ghost"
              disabled={!connected}
              onClick={() => void refreshAssessmentList().catch(() => undefined)}
            >
              {t("common.refresh")}
            </button>
          </div>
          {list?.updatedAt && (
            <p className="hint">{t("home.listUpdated", { time: fmtTime(list.updatedAt, lang) })}</p>
          )}
          {list && list.rows.length === 0 && <p className="muted">{t("home.noAssessments")}</p>}
          <ul className="list">
            {list?.rows.map((r) => (
              <li key={r.id} className="list-item">
                <div className="list-main">
                  <div className="row wrap gap-s">
                    <strong>{t("assess.worker", { code: r.worker_code ?? "?" })}</strong>
                    <SampleBadge show={r.is_sample} />
                    {r.notSynced && <PendingBadge label={t("common.notSynced")} />}
                  </div>
                  <div className="small muted">
                    {t(`home.status.${r.status === "signed_off" ? "signed_off" : "in_progress"}` as Key)} ·{" "}
                    {r.confirmed_nqr_id ? t("home.packConfirmed") : t("home.packNotConfirmed")} ·{" "}
                    {fmtTime(r.created_at, lang)}
                  </div>
                </div>
                <Link to={`/a/${encodeURIComponent(r.id)}/${defaultTab}`} className="btn">
                  {t("home.open")}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
