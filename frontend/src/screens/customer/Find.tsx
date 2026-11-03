// Customers search for workers (no login needed to look) and book one.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, TRADES, type PublicProfile, type Slot, type Trade } from "../../api";
import { Loading, Notice } from "../../components/common";
import { Icon, TRADE_ICON } from "../../components/Icon";
import { BadgeExplain, WorkerCard } from "../../components/WorkerCard";
import { Empty, ErrorBox, Switch, useLoad } from "../../components/ui";
import { useI18n, type Key } from "../../i18n";
import { useSession } from "../../session";
import { useTrades } from "../../trades";
import { lsGet, lsSet, todayIso } from "../../util";

const PINCODE = /^[1-9]\d{5}$/;
const SLOTS: Slot[] = ["morning", "afternoon", "evening"];

export function FindWorkers() {
  const { t, pick } = useI18n();
  const [params, setParams] = useSearchParams();
  const { trades } = useTrades();
  const trade = (TRADES as string[]).includes(params.get("trade") ?? "") ? (params.get("trade") as Trade) : "electrician";
  const [pincode, setPincode] = useState(params.get("pincode") ?? lsGet("hunar.pincode") ?? "");
  const assessed = params.get("assessed") === "1";
  const permit = params.get("permit") === "1";
  const pinOk = pincode === "" || PINCODE.test(pincode);
  const appliedPin = params.get("pincode") ?? "";

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    setParams(next, { replace: true });
  };

  const results = useLoad(
    () => api.searchWorkers({ trade, pincode: appliedPin || undefined, assessed_only: assessed || undefined, permit_only: permit || undefined }),
    [trade, appliedPin, assessed, permit],
  );

  const search = (e: FormEvent) => {
    e.preventDefault();
    if (!pinOk) return;
    lsSet("hunar.pincode", pincode);
    set({ pincode });
  };

  return (
    <div className="stack">
      <h1>{t("find.title")}</h1>
      <form className="card stack" onSubmit={search} noValidate>
        <div className="chip-grid" role="radiogroup" aria-label={t("find.trade")}>
          {TRADES.map((tr) => (
            <button
              key={tr}
              type="button"
              role="radio"
              aria-checked={trade === tr}
              className={`trade-chip ${trade === tr ? "on" : ""}`}
              onClick={() => set({ trade: tr })}
            >
              <Icon name={TRADE_ICON[tr]} size={28} />
              <span>{trades ? pick(trades[tr]?.name) : t(`trade.${tr}` as Key)}</span>
            </button>
          ))}
        </div>
        <label className="field">
          <span className="label">{t("find.pincode")}</span>
          <div className="row gap">
            <input
              type="text"
              inputMode="numeric"
              dir="ltr"
              maxLength={6}
              className="grow"
              value={pincode}
              placeholder="302017"
              onChange={(e) => setPincode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              aria-invalid={!pinOk}
            />
            <button type="submit" className="btn btn-primary" disabled={!pinOk}>
              <Icon name="search" size={20} /> {t("find.search")}
            </button>
          </div>
          <span className="hint">{t("find.pincodeHint")}</span>
        </label>
        {!pinOk && <p className="hint warn-text">{t("common.pincodeInvalid")}</p>}
        <Switch checked={assessed} onChange={(v) => set({ assessed: v ? "1" : null })} label={t("find.assessedOnly")} />
        <Switch checked={permit} onChange={(v) => set({ permit: v ? "1" : null })} label={t("find.permitOnly")} />
        <p className="hint">{t("find.badgesNote")}</p>
      </form>

      <ErrorBox error={results.error} />
      {results.loading && !results.data && <Loading />}
      {results.data && results.data.length === 0 && <Empty icon="search" text={t("find.none")} />}
      {results.data && results.data.length > 0 && (
        <>
          <p className="small muted" role="status">
            {t("find.count", { n: results.data.length })}
          </p>
          <ul className="plain stack">
            {results.data.map((p) => (
              <li key={p.account_id}>
                <Link to={`/c/worker/${p.account_id}${appliedPin ? `?pincode=${appliedPin}` : ""}`} className="card card-link">
                  <WorkerCard p={p} />
                  <span className="card-cta">
                    {t("find.view")} <Icon name="chevron" size={18} className="flip-rtl" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export function WorkerDetail() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const { t } = useI18n();
  const navigate = useNavigate();
  const worker = useLoad(() => api.publicWorker(id), [id]);
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate("/c/find"));
  return (
    <div className="stack">
      <button type="button" className="btn btn-ghost back-btn" onClick={back}>
        <Icon name="chevron" className="flip" /> {t("common.back")}
      </button>
      <ErrorBox error={worker.error} />
      {worker.loading && !worker.data && <Loading />}
      {worker.data && (
        <>
          <section className="card stack">
            <WorkerCard p={worker.data} detailed />
            <h2>{t("find.whatChecked")}</h2>
            <BadgeExplain p={worker.data} />
          </section>
          <BookForm worker={worker.data} defaultPin={params.get("pincode") ?? lsGet("hunar.pincode") ?? ""} />
        </>
      )}
    </div>
  );
}

function BookForm({ worker, defaultPin }: { worker: PublicProfile; defaultPin: string }) {
  const { t, pick, apiText } = useI18n();
  const navigate = useNavigate();
  const { account } = useSession();
  const { trades, error: tradesError } = useTrades();
  const [job, setJob] = useState<string | null>(null);
  const [desc, setDesc] = useState("");
  const [pincode, setPincode] = useState(defaultPin);
  const [date, setDate] = useState(todayIso());
  const [slot, setSlot] = useState<Slot>("morning");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [touched, setTouched] = useState(false);

  const jobs = trades?.[worker.trade]?.jobs ?? {};
  const permitOk = worker.permit.status === "document_checked";
  const permitNote = apiText("trade.permitNote", trades?._permit_note);
  useEffect(() => setJob(null), [worker.account_id]);

  if (!account || account.role !== "customer") {
    return (
      <section className="card stack-s">
        <h2>{t("book.title")}</h2>
        <p>{account ? t("book.customersOnly") : t("book.loginFirst")}</p>
        {!account && (
          <div className="row wrap gap">
            <Link to="/welcome?step=intro&role=customer" className="btn btn-primary grow">
              {t("login.createAccount")}
            </Link>
            <Link to="/login" state={{ from: `/c/worker/${worker.account_id}` }} className="btn grow">
              {t("login.submit")}
            </Link>
          </div>
        )}
      </section>
    );
  }

  const pinOk = PINCODE.test(pincode);
  const dateOk = !!date && date >= todayIso();
  const ok = !!job && pinOk && dateOk;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await api.book({ worker_id: worker.account_id, job_type: job!, description: desc.trim(), pincode, preferred_date: date, slot });
      lsSet("hunar.pincode", pincode);
      navigate("/c/bookings", { state: { booked: true } });
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  };

  return (
    <form className="card stack" onSubmit={(e) => void submit(e)} noValidate>
      <h2>{t("book.title")}</h2>
      <ErrorBox error={tradesError} />
      <fieldset className="field stack-s">
        <legend className="label">{t("book.job")}</legend>
        {Object.entries(jobs).map(([key, j]) => {
          const blocked = j.needs_permit && !permitOk;
          return (
            <label key={key} className={`radio-card ${job === key ? "on" : ""} ${blocked ? "is-disabled" : ""}`}>
              <input type="radio" name="job" value={key} checked={job === key} disabled={blocked} onChange={() => setJob(key)} />
              <span className="grow">
                <span className="block">{pick(j)}</span>
                {j.needs_permit && (
                  <span className={`block small ${blocked ? "warn-text" : "muted"}`}>
                    <Icon name="idcard" size={14} /> {blocked ? t("book.needsPermitBlocked") : t("book.needsPermit")}
                  </span>
                )}
              </span>
            </label>
          );
        })}
        {!permitOk && Object.values(jobs).some((j) => j.needs_permit) && <Notice kind="info">{permitNote}</Notice>}
        {touched && !job && <p className="hint warn-text">{t("book.jobRequired")}</p>}
      </fieldset>
      <label className="field">
        <span className="label">{t("book.describe")}</span>
        <textarea rows={3} maxLength={500} value={desc} onChange={(e) => setDesc(e.target.value)} />
        <span className="hint">{t("book.describeHint")}</span>
      </label>
      <div className="two-col">
        <label className="field">
          <span className="label">{t("book.date")}</span>
          <input type="date" min={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} aria-invalid={touched && !dateOk} />
        </label>
        <label className="field">
          <span className="label">{t("find.pincode")}</span>
          <input
            type="text"
            inputMode="numeric"
            dir="ltr"
            maxLength={6}
            value={pincode}
            onChange={(e) => setPincode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            aria-invalid={touched && !pinOk}
          />
        </label>
      </div>
      {touched && !dateOk && <p className="hint warn-text">{t("book.dateInvalid")}</p>}
      {touched && !pinOk && <p className="hint warn-text">{t("common.pincodeInvalid")}</p>}
      <fieldset className="field">
        <legend className="label">{t("book.slot")}</legend>
        <div className="seg">
          {SLOTS.map((s) => (
            <label key={s} className={`seg-opt ${slot === s ? "on" : ""}`}>
              <input type="radio" name="slot" value={s} checked={slot === s} onChange={() => setSlot(s)} />
              {t(`slot.${s}` as Key)}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="hint">{t("book.phoneNote")}</p>
      <ErrorBox error={error} />
      <button type="submit" className="btn btn-primary btn-block btn-big" disabled={busy}>
        {busy ? t("common.wait") : t("book.send")}
      </button>
    </form>
  );
}
