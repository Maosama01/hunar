import type { PackScore } from "../api";
import { Bar, Notice } from "../components/common";
import { useI18n } from "../i18n";
import { useTrades } from "../trades";
import { useAssessmentCtx } from "./AssessmentLayout";

function PackCard({ pack, confirmed, open }: { pack: PackScore; confirmed: boolean; open: boolean }) {
  const { t } = useI18n();
  return (
    <details className="card pack" open={open}>
      <summary>
        <div className="pack-head">
          <span className="rank">#{pack.rank}</span>
          <div className="grow">
            <div className="row wrap gap-s">
              <strong>{pack.title}</strong>
              {confirmed && <span className="badge badge-signed">✔ {t("mapping.confirmed")}</span>}
            </div>
            <div className="small muted">
              {pack.nsqf_level !== null && t("mapping.nsqf", { level: pack.nsqf_level })} ·{" "}
              {t("mapping.score", { score: pack.score.toFixed(2) })}
            </div>
            <Bar value={pack.score} label={t("mapping.score", { score: pack.score.toFixed(2) })} />
          </div>
        </div>
      </summary>

      <h3>{t("mapping.matched", { n: pack.matched.length })}</h3>
      {pack.matched.length === 0 && <p className="muted">{t("mapping.noMatched")}</p>}
      <ul className="plain stack-s">
        {pack.matched.map((m) => (
          <li key={m.pc_id} className="match">
            <div>
              <code>{m.pc_id}</code> {m.text}
            </div>
            {m.evidence.map((ev, i) => (
              <blockquote key={i} className="quote">
                <span className="small muted">{t("mapping.workerSaid")}: </span>“{ev.sentence}”{" "}
                <span className="small muted">({t("mapping.similarity", { s: ev.similarity.toFixed(2) })})</span>
              </blockquote>
            ))}
          </li>
        ))}
      </ul>

      <h3>{t("mapping.nosCoverage")}</h3>
      <ul className="plain stack-s">
        {pack.nos.map((n) => (
          <li key={n.code ?? n.title}>
            <div className="row wrap gap-s small">
              <code>{n.code ?? "–"}</code>
              {n.core && <span className="badge">{t("mapping.core")}</span>}
              <span className="muted">{t("mapping.nosMatched", { m: n.matched, t: n.total })}</span>
            </div>
            <div className="small">{n.title}</div>
            <Bar value={n.score} label={`${n.code ?? n.title}: ${n.score.toFixed(2)}`} />
          </li>
        ))}
      </ul>

      <details className="sub">
        <summary>{t("mapping.gaps", { n: pack.gaps.length })}</summary>
        <p className="hint">{t("mapping.gapsHint")}</p>
        <ul className="plain stack-s small">
          {pack.gaps.map((g) => (
            <li key={g.pc_id}>
              <code>{g.pc_id}</code> {g.text}
            </li>
          ))}
        </ul>
      </details>
    </details>
  );
}

export function Mapping() {
  const { t, pick } = useI18n();
  const { trades } = useTrades();
  const { view } = useAssessmentCtx();
  const m = view.mapping;

  return (
    <div className="stack">
      <h2>{t("mapping.title")}</h2>
      <section className="card">
        <h3>{t("mapping.declaration")}</h3>
        {view.declaration_text ? (
          <p className="declaration">{view.declaration_text}</p>
        ) : (
          <p className="muted">{t("mapping.empty")}</p>
        )}
      </section>

      {!m && view.declaration_text && (view.createPending || !view.onServer) && (
        <Notice kind="info" role="status">
          💾 {t("mapping.savedOffline")}
        </Notice>
      )}
      {view.trade !== "electrician" ? (
        <Notice kind="info">{t("mapping.otherTrade", { trade: trades ? pick(trades[view.trade]?.name) : view.trade })}</Notice>
      ) : (
        !m && view.declaration_text && view.onServer && !view.createPending && <Notice kind="info">{t("mapping.waiting")}</Notice>
      )}

      {m && (
        <>
          <Notice kind="warn">
            <strong>{t("mapping.suggestionOnly")}</strong>
            <br />
            <span className="small">
              {t("mapping.method", { method: m.method, n: m.sentences.length })} {t("mapping.scoreExplain")}
            </span>
          </Notice>
          {m.ranking.slice(0, 3).map((p, i) => (
            <PackCard key={p.nqr_id} pack={p} confirmed={view.confirmed_nqr_id === p.nqr_id} open={i === 0} />
          ))}
        </>
      )}
    </div>
  );
}
