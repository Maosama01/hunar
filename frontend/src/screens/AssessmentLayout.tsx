import { useEffect } from "react";
import { Navigate, NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";
import { Loading, Notice, PendingBadge, SampleBadge } from "../components/common";
import { tryRefreshAssessment, useAssessmentView, type AssessmentView } from "../data";
import { useI18n } from "../i18n";
import { useSettings } from "../settings";
import { isConnected, useStatus } from "../status";
import { useTrades } from "../trades";

export interface AssessmentCtx {
  view: AssessmentView;
}

export function useAssessmentCtx(): AssessmentCtx {
  return useOutletContext<AssessmentCtx>();
}

export function AssessmentIndex() {
  const { role } = useSettings();
  return <Navigate to={role === "assessor" ? "score" : "mapping"} replace />;
}

export function AssessmentLayout() {
  const { id = "" } = useParams();
  const { t, pick } = useI18n();
  const { trades } = useTrades();
  const view = useAssessmentView(id);
  const connected = isConnected(useStatus());

  // Refresh the server copy whenever we (re)connect; offline the local copy is used.
  useEffect(() => {
    if (connected) void tryRefreshAssessment(id);
  }, [id, connected]);

  if (view === undefined) return <Loading />;
  if (view === null) {
    return <Notice kind="warn">{t("common.notFound")}</Notice>;
  }

  const tabs = [
    ["mapping", t("nav.mapping")],
    ["tasks", t("nav.tasks")],
    ["score", t("nav.score")],
    ["profile", t("nav.profile")],
  ] as const;

  const pending = view.pendingOps.length;

  return (
    <div className="stack">
      <div className="assess-head">
        <div className="row wrap gap-s">
          <h1 className="h-inline">{t("assess.worker", { code: view.worker_code })}</h1>
          <SampleBadge show={view.is_sample} />
          {trades?.[view.trade] && <span className="badge">{pick(trades[view.trade].name)}</span>}
          {!view.onServer && <PendingBadge label={t("assess.notOnServer")} />}
          {view.signedOff && <span className="badge badge-signed">✔ {t("home.status.signed_off")}</span>}
        </div>
        {pending > 0 && <p className="small muted">{t("assess.pendingOps", { n: pending })}</p>}
      </div>
      <nav className="tabs" aria-label="Assessment sections">
        {tabs.map(([path, label]) => (
          <NavLink key={path} to={path} className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
            {label}
          </NavLink>
        ))}
      </nav>
      {view.signedOff && <Notice kind="ok">🔒 {t("assess.frozen")}</Notice>}
      <Outlet context={{ view } satisfies AssessmentCtx} />
    </div>
  );
}
