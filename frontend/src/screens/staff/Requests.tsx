// Assessors pick up workers' requests for a practical assessment. The worker's quiz is shown as a
// self-check for context only: it is not evidence and does not change any score.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type AssessmentRequest, type QuizSummary } from "../../api";
import { Loading, Notice } from "../../components/common";
import { Icon, TRADE_ICON } from "../../components/Icon";
import { Empty, ErrorBox, Ltr, useLoad } from "../../components/ui";
import { refreshAssessment, refreshAssessmentList } from "../../data";
import { useI18n } from "../../i18n";
import { useTrades } from "../../trades";
import { fmtDate } from "../../util";

function QuizContext({ q }: { q: QuizSummary }) {
  const { t, lang, pick } = useI18n();
  return (
    <details className="sub quiz-context">
      <summary>
        {t("requests.quiz", {
          lo: Math.round(q.expected_percent_interval90[0]),
          hi: Math.round(q.expected_percent_interval90[1]),
        })}
      </summary>
      <Notice kind="info">{t("requests.quizContextOnly")}</Notice>
      <ul className="plain small stack-s">
        <li>{t("requests.quizWhen", { date: fmtDate(q.finished_at, lang), n: q.attempts_finished })}</li>
        <li>{t("quiz.counts", { n: q.n_answered, dk: q.n_dont_know })}</li>
        {q.n_rapid > 0 && <li className="warn-text">{t("quiz.rapidCount", { n: q.n_rapid })}</li>}
      </ul>
      <table className="mini-table small">
        <tbody>
          {q.by_nos.map((n) => (
            <tr key={n.nos}>
              <td>
                <code>{n.nos}</code> {pick(n.title)}
              </td>
              <td className="nowrap">{n.enough ? t("quiz.correctOf", { c: n.correct, n: n.answered }) : t("quiz.notEnough")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="fine-print">
        {t("quiz.bankDraft", { v: q.bank.version })} {!q.bank.calibrated && t("quiz.uncalibrated")}
      </p>
    </details>
  );
}

function RequestCard({ r }: { r: AssessmentRequest }) {
  const { t, lang, pick } = useI18n();
  const navigate = useNavigate();
  const { trades } = useTrades();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.startRequest(r.id);
      // Load the new assessment into this device's copy, then open the existing assessor flow.
      await refreshAssessment(res.assessment_id).catch(() => undefined);
      await refreshAssessmentList().catch(() => undefined);
      navigate(`/a/${encodeURIComponent(res.assessment_id)}/mapping`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };
  return (
    <li className="card stack-s">
      <div className="row gap-s">
        <span className="avatar small-avatar" aria-hidden="true">
          <Icon name={TRADE_ICON[r.trade] ?? "user"} size={20} />
        </span>
        <div className="grow">
          <strong>{r.worker_display_name ?? "?"}</strong>
          <div className="small muted">
            {trades ? pick(trades[r.trade]?.name) : r.trade} · <Ltr>{r.pincode}</Ltr> · {t("assess.sentOn", { date: fmtDate(r.created_at, lang) })}
            {r.preferred_date ? ` · ${t("assess.preferred", { date: fmtDate(r.preferred_date, lang) })}` : ""}
          </div>
        </div>
      </div>
      <div>
        <span className="label-inline">{t("mapping.declaration")}</span>
        {r.declaration_text ? <p className="declaration">{r.declaration_text}</p> : <p className="muted">{t("mapping.empty")}</p>}
      </div>
      {r.quiz ? <QuizContext q={r.quiz} /> : <p className="small muted">{t("requests.noQuiz")}</p>}
      <ErrorBox error={error} />
      <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void start()}>
        {busy ? t("common.wait") : t("requests.start")}
      </button>
    </li>
  );
}

export function Requests() {
  const { t } = useI18n();
  const list = useLoad(() => api.assessmentRequests(), []);
  return (
    <div className="stack">
      <div className="row between gap">
        <h1 className="h-inline">{t("requests.title")}</h1>
        <button type="button" className="btn btn-small" onClick={() => void list.reload()} disabled={list.loading}>
          <Icon name="refresh" size={18} /> {t("common.refresh")}
        </button>
      </div>
      <p className="muted">{t("requests.intro")}</p>
      <ErrorBox error={list.error} />
      {list.loading && !list.data && <Loading />}
      {list.data && list.data.length === 0 && <Empty icon="inbox" text={t("requests.none")} />}
      <ul className="plain stack">
        {list.data?.map((r) => (
          <RequestCard key={r.id} r={r} />
        ))}
      </ul>
    </div>
  );
}
