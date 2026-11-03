// Admin: record that the worker's State electrical permit document was seen (or clear that record).
import { useState } from "react";
import { api, TRADES, type PublicProfile, type Trade } from "../../api";
import { Loading, Notice } from "../../components/common";
import { Icon, TRADE_ICON } from "../../components/Icon";
import { WorkerCard } from "../../components/WorkerCard";
import { Empty, ErrorBox, useLoad } from "../../components/ui";
import { useI18n, type Key } from "../../i18n";
import { useTrades } from "../../trades";

function PermitRow({ p, onDone }: { p: PublicProfile; onDone: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState(p.permit.state);
  const [seen, setSeen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const checked = p.permit.status === "document_checked";

  const save = async (status: "document_checked" | "self_declared") => {
    setBusy(true);
    setError(null);
    try {
      await api.setPermit(p.account_id, status, state.trim());
      setOpen(false);
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="card stack-s">
      <WorkerCard p={p} />
      <p className="small">
        <strong>{t("permits.status")}</strong> {t(`permits.st.${p.permit.status}` as Key)}
        {p.permit.state ? ` (${p.permit.state})` : ""}
      </p>
      <ErrorBox error={error} />
      {!open ? (
        <div className="row wrap gap">
          {!checked && (
            <button type="button" className="btn btn-primary grow" onClick={() => setOpen(true)}>
              <Icon name="idcard" /> {t("permits.mark")}
            </button>
          )}
          {checked && (
            <button type="button" className="btn btn-danger-outline grow" disabled={busy} onClick={() => void save("self_declared")}>
              {t("permits.clear")}
            </button>
          )}
        </div>
      ) : (
        <div className="stack-s">
          <label className="field">
            <span className="label">{t("wprofile.permitState")}</span>
            <input type="text" maxLength={40} value={state} onChange={(e) => setState(e.target.value)} />
          </label>
          <label className="check">
            <input type="checkbox" checked={seen} onChange={(e) => setSeen(e.target.checked)} />
            <span>{t("permits.seen")}</span>
          </label>
          <div className="row wrap gap">
            <button type="button" className="btn btn-primary grow" disabled={!seen || !state.trim() || busy} onClick={() => void save("document_checked")}>
              {t("permits.confirm")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

export function Permits() {
  const { t, pick } = useI18n();
  const { trades } = useTrades();
  const [trade, setTrade] = useState<Trade>("electrician");
  const list = useLoad(() => api.adminWorkers({ trade }), [trade]);
  return (
    <div className="stack">
      <h1>{t("permits.title")}</h1>
      <p className="muted">{t("permits.intro")}</p>
      <Notice kind="info">{t("permits.onlyVisible")}</Notice>
      <div className="chip-grid" role="radiogroup">
        {TRADES.map((tr) => (
          <button key={tr} type="button" role="radio" aria-checked={trade === tr} className={`trade-chip ${trade === tr ? "on" : ""}`} onClick={() => setTrade(tr)}>
            <Icon name={TRADE_ICON[tr]} size={24} />
            <span>{trades ? pick(trades[tr]?.name) : tr}</span>
          </button>
        ))}
      </div>
      <ErrorBox error={list.error} />
      {list.loading && !list.data && <Loading />}
      {list.data && list.data.length === 0 && <Empty icon="users" text={t("find.none")} />}
      <ul className="plain stack">
        {list.data?.map((p) => (
          <PermitRow key={p.account_id} p={p} onDone={() => void list.reload()} />
        ))}
      </ul>
    </div>
  );
}
