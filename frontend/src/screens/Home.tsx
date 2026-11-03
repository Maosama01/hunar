import { useEffect } from "react";
import { Link } from "react-router-dom";
import { PendingBadge, SampleBadge } from "../components/common";
import { Icon } from "../components/Icon";
import { refreshAssessmentList, useAssessmentList } from "../data";
import { useI18n, type Key } from "../i18n";
import { useSession } from "../session";
import { isConnected, useStatus } from "../status";
import { fmtTime } from "../util";

/** Staff home: what this role can do, and the list of assessments. */
export function Home() {
  const { t, lang } = useI18n();
  const { account } = useSession();
  const role = account?.role ?? null;
  const list = useAssessmentList();
  const status = useStatus();
  const connected = isConnected(status);

  useEffect(() => {
    if (connected) void refreshAssessmentList().catch(() => undefined);
  }, [connected]);

  const defaultTab = role === "assessor" ? "score" : "mapping";
  const assessor = role === "assessor" || role === "admin";

  return (
    <div className="stack">
      <section className="card stack-s">
        <h1>{t("app.tagline")}</h1>
        <p>{t("home.intro")}</p>
        {account && (
          <p className="small muted">
            {t("home.loggedInAs", { name: account.display_name, role: t(`roles.${role}` as Key) })}
          </p>
        )}
      </section>

      <section className="card stack-s" aria-labelledby="actions-h">
        <h2 id="actions-h">{t("home.actions")}</h2>
        <div className="action-grid">
          <Link to="/declare" className="action">
            <Icon name="plus" size={28} />
            <span>{t("home.newDeclaration")}</span>
          </Link>
          {assessor && (
            <Link to="/staff/requests" className="action">
              <Icon name="inbox" size={28} />
              <span>{t("nav.requests")}</span>
            </Link>
          )}
          {role === "admin" && (
            <Link to="/staff/permits" className="action">
              <Icon name="idcard" size={28} />
              <span>{t("permits.title")}</span>
            </Link>
          )}
          {assessor && (
            <Link to="/admin" className="action">
              <Icon name="file" size={28} />
              <span>{t("home.openAdmin")}</span>
            </Link>
          )}
          <Link to="/rater" className="action">
            <Icon name="users" size={28} />
            <span>{t("home.openRater")}</span>
          </Link>
        </div>
        {role === "assessor" && <p className="hint">{t("home.assessorHint")}</p>}
      </section>

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
        {list?.updatedAt && <p className="hint">{t("home.listUpdated", { time: fmtTime(list.updatedAt, lang) })}</p>}
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
                  {r.confirmed_nqr_id ? t("home.packConfirmed") : t("home.packNotConfirmed")} · {fmtTime(r.created_at, lang)}
                </div>
              </div>
              <Link to={`/a/${encodeURIComponent(r.id)}/${defaultTab}`} className="btn">
                {t("home.open")}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
