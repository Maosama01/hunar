// Adaptive self-check quiz: choose a trade, one question per screen, result with its uncertainty,
// then a review with explanations. A self-check for the worker, never a certificate or a badge.
// Compulsory for workers: the first one starts when they register, and until one is finished the app
// shows only the quiz (see RequireQuiz in App.tsx). A quiz rushed through (more than half the answers
// faster than reading time) does not count and has to be taken again.
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, TRADES, type QuizItem, type QuizResult, type Trade, type TranslationStatus } from "../../api";
import { Loading, Notice } from "../../components/common";
import { Icon, TRADE_ICON } from "../../components/Icon";
import { Empty, ErrorBox, SpeakButton, useLoad } from "../../components/ui";
import { useI18n } from "../../i18n";
import { endonym, langInfo } from "../../i18n/languages";
import { quizPending, updateAccount, useSession } from "../../session";
import { useTrades } from "../../trades";
import { clamp01, fmtDate } from "../../util";

/** Says when a question is machine-translated or not available in the chosen language. */
export function TranslationLabel({ status }: { status: TranslationStatus }) {
  const { t, lang } = useI18n();
  if (status === "machine") return <span className="badge badge-machine">{t("quiz.trMachine")}</span>;
  if (status === "missing") return <span className="badge badge-machine">{t("quiz.trMissing", { lang: endonym(lang) })}</span>;
  return null;
}

// ---- Start + history ------------------------------------------------------------------------------

export function QuizHome() {
  const { t, lang, pick, langOf } = useI18n();
  const navigate = useNavigate();
  const { account } = useSession();
  const banks = useLoad(() => api.quizBanks(), []);
  const attempts = useLoad(() => api.quizAttempts(), []);
  const profile = useLoad(() => api.myProfile(), []);
  const { trades } = useTrades();
  const [trade, setTrade] = useState<Trade | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const consentOk = !!account?.consents.assessment;
  const pending = quizPending(account);
  const open = account?.quiz?.in_progress ?? null;

  useEffect(() => {
    if (trade || !banks.data) return;
    const mine = profile.data?.trade ?? open?.trade;
    if (mine && banks.data[mine]) setTrade(mine);
    else {
      const first = TRADES.find((x) => banks.data![x]);
      if (first) setTrade(first);
    }
  }, [banks.data, profile.data, trade, open?.trade]);

  const agree = async () => {
    setBusy(true);
    setError(null);
    try {
      updateAccount(await api.setConsent("assessment", true));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    if (!trade) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.startQuiz(trade, lang);
      navigate(`/w/quiz/${r.attempt_id}`, { state: { item: r.item } });
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };

  const bank = trade ? banks.data?.[trade] : undefined;
  const lastFinished = attempts.data?.find((a): a is QuizResult => "expected_percent" in a);
  const lastRushed = pending && !!lastFinished && !lastFinished.counts;
  const intro = t("quiz.intro", { min: bank?.rules.min_items ?? 12, max: bank?.rules.max_items ?? 25 });

  return (
    <div className="stack">
      <h1>{t("quiz.title")}</h1>
      {pending && (
        <Notice kind="info">
          <strong className="block">{t("quiz.requiredFirst")}</strong>
          {t("quiz.requiredWhy")}
        </Notice>
      )}
      {lastRushed && (
        <Notice kind="warn" role="alert">
          {t("quiz.lastNotCounted")}
        </Notice>
      )}
      {pending && open && (
        <Link to={`/w/quiz/${open.attempt_id}`} className="btn btn-primary btn-block btn-big">
          {t("quiz.continueFirst")}
        </Link>
      )}
      <section className="card stack-s">
        <p>{intro}</p>
        <p>
          <strong>{t("quiz.dontGuess")}</strong>
        </p>
        <p className="small muted">{t("quiz.notCertificate")}</p>
        <SpeakButton text={`${intro} ${t("quiz.dontGuess")} ${t("quiz.notCertificate")}`} lang={langOf("quiz.intro")} />
      </section>

      {!consentOk && (
        <Notice kind="warn">
          <span className="block">
            {t("quiz.needConsent")} <Link to="/w/privacy">{t("nav.privacy")}</Link>
          </span>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void agree()}>
            {t("quiz.agreeAndStart")}
          </button>
        </Notice>
      )}

      <section className="card stack">
        <h2>{t("quiz.chooseTrade")}</h2>
        <ErrorBox error={banks.error} />
        {banks.loading && !banks.data && <Loading />}
        <div className="chip-grid" role="radiogroup" aria-label={t("quiz.chooseTrade")}>
          {TRADES.map((tr) => {
            const has = !!banks.data?.[tr];
            return (
              <button
                key={tr}
                type="button"
                role="radio"
                aria-checked={trade === tr}
                className={`trade-chip ${trade === tr ? "on" : ""}`}
                disabled={!has}
                onClick={() => setTrade(tr)}
              >
                <Icon name={TRADE_ICON[tr]} size={28} />
                <span>{trades ? pick(trades[tr]?.name) : t(`trade.${tr}`)}</span>
                {banks.data && !has && <span className="chip-note">{t("quiz.comingSoon")}</span>}
              </button>
            );
          })}
        </div>
        <ErrorBox error={error} />
        <button type="button" className="btn btn-primary btn-block btn-big" disabled={!trade || !bank || busy || !consentOk} onClick={() => void start()}>
          {busy ? t("common.wait") : t("quiz.start")}
        </button>
        <p className="hint">{t("quiz.noBack")}</p>
      </section>

      <section className="card stack-s">
        <h2>{t("quiz.history")}</h2>
        <ErrorBox error={attempts.error} />
        {attempts.data && attempts.data.length === 0 && <Empty icon="quiz" text={t("quiz.noHistory")} />}
        <ul className="list">
          {attempts.data?.map((a) => (
            <li key={a.attempt_id} className="list-item">
              <span className="avatar small-avatar" aria-hidden="true">
                <Icon name={TRADE_ICON[a.trade] ?? "quiz"} size={20} />
              </span>
              <div className="list-main">
                <strong>{trades ? pick(trades[a.trade]?.name) : a.trade}</strong>
                {"expected_percent" in a ? (
                  <div className="small muted">
                    {fmtDate(a.finished_at, lang)} ·{" "}
                    {t("quiz.rangeShort", { lo: Math.round(a.expected_percent_interval90[0]), hi: Math.round(a.expected_percent_interval90[1]) })}
                    {!a.counts && <span className="warn-text"> · {t("quiz.notCountedShort")}</span>}
                  </div>
                ) : (
                  <div className="small muted">{t("quiz.unfinished", { n: a.n_answered })}</div>
                )}
              </div>
              <Link to={`/w/quiz/${a.attempt_id}`} className="btn btn-small">
                {"expected_percent" in a ? t("quiz.seeResult") : t("quiz.continue")}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

// ---- One question per screen ------------------------------------------------------------------------

export function QuizRun() {
  const { id = "" } = useParams();
  const { t, pickL } = useI18n();
  const location = useLocation();
  const { account } = useSession();
  const navState = location.state as { item?: QuizItem; welcome?: boolean } | null;
  const initial = navState?.item ?? null;
  const [item, setItem] = useState<QuizItem | null>(initial);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [rapid, setRapid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const shownAt = useRef(performance.now());

  const load = async () => {
    setLoadError(null);
    try {
      const r = await api.quizAttempt(id);
      if (r.done) {
        setResult(r.result);
        setItem(null);
        refreshAccount();
      } else setItem((cur) => (cur?.id === r.item.id ? cur : r.item));
    } catch (e) {
      setLoadError(e);
    }
  };

  // Always ask the server: the item passed in navigation state is only a placeholder, and history
  // state survives a reload (the attempt may have moved on or finished since).
  useEffect(() => {
    setResult(null);
    setRapid(false);
    setItem(navState?.item ?? null);
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // The clock starts when a question appears.
  useEffect(() => {
    shownAt.current = performance.now();
    setSelected(null);
    window.scrollTo(0, 0);
  }, [item?.id]);

  const answer = async (choice: number | null) => {
    if (!item || busy) return;
    setBusy(true);
    setError(null);
    const seconds = Math.round((performance.now() - shownAt.current) / 100) / 10;
    try {
      const r = await api.answerQuiz(id, { item_id: item.id, choice, seconds });
      if (r.done) {
        setResult(r.result);
        setItem(null);
        refreshAccount();
      } else {
        setRapid(r.rapid_warning);
        setItem(r.item);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) await load(); // already answered: show the current one
      else setError(e);
    } finally {
      setBusy(false);
    }
  };

  if (result) return <QuizResultView result={result} />;
  if (loadError) return <ErrorBox error={loadError} />;
  if (!item) return <Loading />;

  const readAll = `${item.stem}. ${item.options.map((o, i) => `${i + 1}. ${o}`).join(". ")}`;
  const [nosTitle, nosLang] = pickL(item.nos_title);
  return (
    <div className="stack quiz">
      {navState?.welcome && item.position === 1 && (
        <Notice kind="ok" role="status">
          {t("quiz.welcomeFirst", { name: account?.display_name ?? "" })}
        </Notice>
      )}
      <div className="quiz-progress">
        <div className="row between small">
          <span>{t("quiz.progress", { n: item.position, max: item.max_items })}</span>
          <span className="muted">{t("quiz.selfCheck")}</span>
        </div>
        <div className="bar" aria-hidden="true">
          <div className="bar-fill tone-brand" style={{ width: `${clamp01(item.position / item.max_items) * 100}%` }} />
        </div>
      </div>
      {rapid && (
        <Notice kind="info" role="status">
          {t("quiz.rapid")}
        </Notice>
      )}
      {/* The question follows its own language's direction (e.g. Hindi fallback inside the Urdu UI). */}
      <section className="card stack" dir={langInfo(item.language).dir} lang={item.language}>
        <div className="row wrap gap-s">
          <span className="small muted" lang={nosLang}>
            {nosTitle}
          </span>
          <TranslationLabel status={item.translation} />
        </div>
        <h1 className="quiz-stem" lang={item.language}>
          {item.stem}
        </h1>
        {item.image && <img src={item.image} alt="" className="quiz-img" />}
        <SpeakButton text={readAll} lang={item.language} />
        <div className="options" role="radiogroup" aria-label={t("quiz.options")}>
          {item.options.map((o, i) => (
            <button
              key={i}
              type="button"
              role="radio"
              aria-checked={selected === i}
              className={`option ${selected === i ? "on" : ""}`}
              onClick={() => setSelected(i)}
              disabled={busy}
            >
              <span className="option-n" aria-hidden="true">
                {i + 1}
              </span>
              <span className="option-text" lang={item.language}>
                {o}
              </span>
            </button>
          ))}
        </div>
      </section>
      <ErrorBox error={error} />
      <button type="button" className="btn btn-primary btn-block btn-big" disabled={selected === null || busy} onClick={() => void answer(selected)}>
        {busy ? t("common.wait") : t("quiz.next")}
      </button>
      <button type="button" className="btn btn-block dont-know" disabled={busy} onClick={() => void answer(null)}>
        {t("quiz.dontKnow")}
      </button>
      <p className="hint center">{t("quiz.noBack")}</p>
    </div>
  );
}

/** A finished quiz lifts the gate: reload the account so the other worker screens open. */
function refreshAccount() {
  void api.me().then(updateAccount).catch(() => undefined);
}

// ---- Result ----------------------------------------------------------------------------------------

function RangeBar({ lo, hi, mid }: { lo: number; hi: number; mid: number }) {
  const { t } = useI18n();
  const L = clamp01(lo / 100) * 100;
  const H = clamp01(hi / 100) * 100;
  return (
    <div className="range" role="img" aria-label={t("quiz.rangeAria", { lo: Math.round(lo), hi: Math.round(hi) })}>
      <div className="range-track">
        <div className="range-band" style={{ insetInlineStart: `${L}%`, width: `${Math.max(1, H - L)}%` }} />
        <div className="range-mid" style={{ insetInlineStart: `${clamp01(mid / 100) * 100}%` }} />
      </div>
      <div className="range-scale small muted" aria-hidden="true">
        <span>0%</span>
        <span>50%</span>
        <span>100%</span>
      </div>
    </div>
  );
}

export function QuizResultView({ result }: { result: QuizResult }) {
  const { t, lang, pick, apiText, langOf } = useI18n();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const lo = Math.round(result.expected_percent_interval90[0]);
  const hi = Math.round(result.expected_percent_interval90[1]);
  const headline = t("quiz.resultLine", { lo, hi });
  const draft = result.bank.status.trim().toUpperCase().startsWith("DRAFT");
  // After the first quiz the next step is the profile (trade, PIN code); a practical assessment needs it.
  const profile = useLoad(() => api.myProfile(), []);
  const noProfile = profile.data === null;

  const retake = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.startQuiz(result.trade, lang);
      navigate(`/w/quiz/${r.attempt_id}`, { state: { item: r.item } });
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="row wrap gap-s">
        <h1 className="h-inline">{t("quiz.resultTitle")}</h1>
        <span className="badge">{t("quiz.selfCheck")}</span>
      </div>
      {!result.counts && (
        <Notice kind="warn" role="alert">
          <strong className="block">{t("quiz.notCountedTitle")}</strong>
          {t("quiz.notCountedBody", { n: result.n_rapid, total: result.n_answered, pct: Math.round(result.min_read_share * 100) })}
        </Notice>
      )}
      <section className="card stack">
        <p className="result-line">{headline}</p>
        <RangeBar lo={result.expected_percent_interval90[0]} hi={result.expected_percent_interval90[1]} mid={result.expected_percent} />
        <p className="small muted">{t("quiz.rangeExplain")}</p>
        <SpeakButton text={headline} lang={langOf("quiz.resultLine")} />
        <ul className="plain small stack-s">
          <li>{t("quiz.counts", { n: result.n_answered, dk: result.n_dont_know })}</li>
          {result.n_rapid > 0 && <li className="warn-text">{t("quiz.rapidCount", { n: result.n_rapid })}</li>}
        </ul>
      </section>

      <section className="card stack-s">
        <h2>{t("quiz.byTopic")}</h2>
        {result.by_nos.map((n) => (
          <div key={n.nos} className="nos-row">
            <div className="row between gap-s">
              <span>{pick(n.title)}</span>
              <span className="small nowrap">
                {n.answered ? t("quiz.correctOf", { c: n.correct, n: n.answered }) : t("quiz.notAsked")}
              </span>
            </div>
            {n.enough ? (
              <div className="bar" aria-hidden="true">
                <div className="bar-fill tone-brand" style={{ width: `${n.answered ? (n.correct / n.answered) * 100 : 0}%` }} />
              </div>
            ) : (
              <p className="small muted">{t("quiz.notEnough")}</p>
            )}
          </div>
        ))}
      </section>

      <section className="card stack-s">
        <h2>{t("quiz.revise")}</h2>
        {result.revise.length === 0 ? (
          <p className="muted">{t("quiz.reviseNone")}</p>
        ) : (
          <ul className="revise">
            {result.revise.map((n) => (
              <li key={n.nos}>{pick(n.title)}</li>
            ))}
          </ul>
        )}
      </section>

      <Notice kind="info">{apiText("quiz.note", result.note)}</Notice>

      <ErrorBox error={error} />
      {!result.counts ? (
        <button type="button" className="btn btn-primary btn-block btn-big" disabled={busy} onClick={() => void retake()}>
          <Icon name="refresh" /> {busy ? t("common.wait") : t("quiz.retake")}
        </button>
      ) : noProfile ? (
        <Link to="/w/profile" state={{ welcome: true }} className="btn btn-primary btn-block btn-big">
          <Icon name="user" /> {t("quiz.nextProfile")}
        </Link>
      ) : (
        <Link to="/w/assess" className="btn btn-primary btn-block btn-big">
          <Icon name="clipboard" /> {t("quiz.requestPractical")}
        </Link>
      )}
      <Link to={`/w/quiz/${result.attempt_id}/review`} className="btn btn-block">
        <Icon name="book" /> {t("quiz.review")}
      </Link>
      <Link to="/w/quiz" className="btn btn-ghost btn-block">
        {t("quiz.backToStart")}
      </Link>

      <p className="fine-print">
        {draft ? t("quiz.bankDraft", { v: result.bank.version }) : t("quiz.bankVersion", { v: result.bank.version })}{" "}
        {!result.bank.calibrated && apiText("quiz.uncalibrated", result.calibration_note)}
      </p>
    </div>
  );
}

// ---- Review ----------------------------------------------------------------------------------------

export function QuizReview() {
  const { id = "" } = useParams();
  const { t, lang } = useI18n();
  const review = useLoad(() => api.quizReview(id), [id]);
  return (
    <div className="stack">
      <div className="row between gap">
        <h1 className="h-inline">{t("quiz.reviewTitle")}</h1>
        <Link to={`/w/quiz/${id}`} className="btn btn-small">
          {t("quiz.seeResult")}
        </Link>
      </div>
      <p className="muted">{t("quiz.reviewIntro")}</p>
      <ErrorBox error={review.error} />
      {review.loading && !review.data && <Loading />}
      {review.data?.map((r) => (
        <section
          key={r.position}
          className={`card stack-s review-item ${r.correct ? "is-right" : "is-wrong"}`}
          lang={r.translation === "missing" ? "hi" : lang}
          dir={langInfo(r.translation === "missing" ? "hi" : lang).dir}
        >
          <div className="row wrap gap-s between">
            <strong>{t("quiz.qn", { n: r.position })}</strong>
            <span className="row gap-s">
              <TranslationLabel status={r.translation} />
              <span className={`badge ${r.correct ? "badge-right" : "badge-wrong"}`}>
                {r.your_choice === null ? t("quiz.youDontKnow") : r.correct ? t("quiz.right") : t("quiz.wrong")}
              </span>
            </span>
          </div>
          <p className="review-stem">{r.stem}</p>
          <ol className="plain stack-s">
            {r.options.map((o, i) => (
              <li key={i} className={`review-opt ${i === r.answer ? "is-answer" : ""} ${i === r.your_choice && i !== r.answer ? "is-yours" : ""}`}>
                <span className="option-n" aria-hidden="true">
                  {i + 1}
                </span>
                <span className="grow">
                  {o}
                  {i === r.answer && <span className="block small strong">✓ {t("quiz.correctAnswer")}</span>}
                  {i === r.your_choice && i !== r.answer && <span className="block small">{t("quiz.yourAnswer")}</span>}
                </span>
              </li>
            ))}
          </ol>
          {r.rapid && <p className="small warn-text">{t("quiz.rapidItem")}</p>}
          <p>
            <strong>{t("quiz.why")}</strong> {r.explanation}
          </p>
          <details className="sub">
            <summary>{t("quiz.sources", { n: r.sources.length })}</summary>
            <ul className="small">
              {r.sources.map((s, i) => (
                <li key={i} lang="en">
                  {s}
                </li>
              ))}
            </ul>
          </details>
        </section>
      ))}
    </div>
  );
}
