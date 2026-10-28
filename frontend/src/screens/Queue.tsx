import { Link } from "react-router-dom";
import { Notice } from "../components/common";
import { kindKey } from "../components/Layout";
import { useLive } from "../data";
import { db } from "../db";
import { useI18n, type Key } from "../i18n";
import { useStatus } from "../status";
import { fmtTime } from "../util";

/** The outbox, oldest first: what is waiting to reach the server. Photos are not shown here. */
export function Queue() {
  const { t, lang } = useI18n();
  const status = useStatus();
  const ops = useLive(() => db.outbox.orderBy("seq").toArray(), []);
  const ratings = useLive(() => db.ratings.count(), []);

  return (
    <div className="stack">
      <h1>{t("queue.title")}</h1>
      <p className="muted">{t("queue.explain")}</p>
      {status.lastError && <Notice kind="warn">{status.lastError}</Notice>}
      {ops && ops.length === 0 && !ratings && <Notice kind="ok">✔ {t("queue.empty")}</Notice>}
      {ops && ops.length > 0 && (
        <ol className="plain stack-s" aria-label={t("queue.title")}>
          {ops.map((op) => (
            <li key={op.op_id} className={`card queue-op op-${op.status}`} data-kind={op.kind} data-status={op.status}>
              <div className="row between wrap gap-s">
                <strong>
                  #{op.seq} · {t(kindKey(op.kind))}
                </strong>
                <span className={`badge badge-${op.status === "rejected" ? "critical" : "pending"}`}>
                  {t(`queue.status.${op.status}` as Key)}
                </span>
              </div>
              <div className="small muted">
                {fmtTime(op.created_at, lang)}
                {op.assessment_id && (
                  <>
                    {" · "}
                    <Link to={`/a/${op.assessment_id}`}>{t("queue.assessment", { id: op.assessment_id.slice(0, 8) })}</Link>
                  </>
                )}
              </div>
              {op.error && <div className="small warn-text">{op.error}</div>}
            </li>
          ))}
        </ol>
      )}
      {!!ratings && <Notice kind="info">{t("queue.ratings", { n: ratings })}</Notice>}
    </div>
  );
}
