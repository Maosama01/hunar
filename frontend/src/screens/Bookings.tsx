// Bookings for both sides. Phone numbers appear only after the worker accepts.
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, type Booking, type BookingStatus } from "../api";
import { Loading, Notice } from "../components/common";
import { Icon, TRADE_ICON } from "../components/Icon";
import { Empty, ErrorBox, Ltr, StarInput, Stars, useLoad } from "../components/ui";
import { useI18n, type Key } from "../i18n";
import { useSession } from "../session";
import { fmtDate } from "../util";

const STATUS: Record<BookingStatus, { key: Key; workerKey?: Key; cls: string }> = {
  requested: { key: "booking.status.requested", workerKey: "booking.status.requestedWorker", cls: "st-wait" },
  accepted: { key: "booking.status.accepted", cls: "st-ok" },
  declined: { key: "booking.status.declined", cls: "st-off" },
  cancelled: { key: "booking.status.cancelled", cls: "st-off" },
  completed: { key: "booking.status.completed", cls: "st-done" },
};

function formatPhone(p: string): string {
  const d = p.replace(/^\+91/, "");
  return d.length === 10 ? `+91 ${d.slice(0, 5)} ${d.slice(5)}` : p;
}

function RateForm({ b, onDone }: { b: Booking; onDone: (b: Booking) => void }) {
  const { t } = useI18n();
  const [stars, setStars] = useState(0);
  const [review, setReview] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      onDone(await api.rateBooking(b.id, stars, review.trim()));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rate stack-s">
      <strong>{t("booking.rateTitle", { name: b.other_party.display_name })}</strong>
      <StarInput value={stars} onChange={setStars} />
      <label className="field">
        <span className="label small">{t("booking.review")}</span>
        <textarea rows={2} maxLength={300} value={review} onChange={(e) => setReview(e.target.value)} />
      </label>
      <ErrorBox error={error} />
      <button type="button" className="btn btn-primary" disabled={stars === 0 || busy} onClick={() => void send()}>
        {t("booking.sendRating")}
      </button>
    </div>
  );
}

function BookingCard({ b, onChange }: { b: Booking; onChange: (b: Booking) => void }) {
  const { t, lang, pick } = useI18n();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const st = STATUS[b.status];
  const isWorker = b.you_are === "worker";

  const act = async (action: "accept" | "decline" | "cancel" | "complete") => {
    setBusy(action);
    setError(null);
    try {
      onChange(await api.bookingAction(b.id, action));
      setConfirmCancel(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  const open = b.status === "requested" || b.status === "accepted";
  return (
    <li className="card booking stack-s">
      <div className="row between gap-s wrap">
        <span className={`status ${st.cls}`}>{t(isWorker && st.workerKey ? st.workerKey : st.key)}</span>
        <span className="small muted">{fmtDate(b.preferred_date, lang)} · {t(`slot.${b.slot}` as Key)}</span>
      </div>
      <div className="row gap-s">
        <span className="avatar small-avatar" aria-hidden="true">
          <Icon name={TRADE_ICON[b.trade] ?? "briefcase"} size={20} />
        </span>
        <div className="grow">
          <strong>{b.job ? pick(b.job) : b.job_type}</strong>
          <div className="small muted">
            {t(isWorker ? "booking.customer" : "booking.worker", { name: b.other_party.display_name })} · <Ltr>{b.pincode}</Ltr>
          </div>
        </div>
      </div>
      {b.description && <p className="quote">{b.description}</p>}

      {b.other_party.phone ? (
        <a className="btn btn-block phone-btn" href={`tel:${b.other_party.phone}`}>
          <Icon name="phone" /> {t("booking.call", { name: b.other_party.display_name })} <Ltr>{formatPhone(b.other_party.phone)}</Ltr>
        </a>
      ) : (
        open && <p className="hint">{t("booking.phoneAfterAccept")}</p>
      )}

      {b.rating !== null && (
        <div className="small">
          {t("booking.rated")} <Stars value={b.rating} />
          {b.review && <span className="block muted">“{b.review}”</span>}
        </div>
      )}

      <ErrorBox error={error} />
      <div className="row wrap gap">
        {isWorker && b.status === "requested" && (
          <>
            <button type="button" className="btn btn-primary grow" disabled={!!busy} onClick={() => void act("accept")}>
              {t("booking.accept")}
            </button>
            <button type="button" className="btn grow" disabled={!!busy} onClick={() => void act("decline")}>
              {t("booking.decline")}
            </button>
          </>
        )}
        {b.status === "accepted" && (
          <button type="button" className="btn btn-primary grow" disabled={!!busy} onClick={() => void act("complete")}>
            {t("booking.complete")}
          </button>
        )}
        {open && !(isWorker && b.status === "requested") && !confirmCancel && (
          <button type="button" className="btn btn-danger-outline grow" disabled={!!busy} onClick={() => setConfirmCancel(true)}>
            {t("booking.cancel")}
          </button>
        )}
        {confirmCancel && (
          <>
            <button type="button" className="btn btn-danger grow" disabled={!!busy} onClick={() => void act("cancel")}>
              {t("booking.cancelConfirm")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setConfirmCancel(false)}>
              {t("common.no")}
            </button>
          </>
        )}
      </div>
      {!isWorker && b.status === "completed" && b.rating === null && <RateForm b={b} onDone={onChange} />}
    </li>
  );
}

export function BookingsScreen() {
  const { t } = useI18n();
  const { account } = useSession();
  const location = useLocation();
  const justBooked = (location.state as { booked?: boolean } | null)?.booked;
  const list = useLoad(() => api.bookings(), []);
  const isWorker = account?.role === "worker";
  const replace = (b: Booking) => list.setData((rows) => rows?.map((r) => (r.id === b.id ? b : r)));
  const rows = list.data ?? [];
  const active = rows.filter((b) => b.status === "requested" || b.status === "accepted");
  const past = rows.filter((b) => !(b.status === "requested" || b.status === "accepted"));

  return (
    <div className="stack">
      <div className="row between gap">
        <h1 className="h-inline">{t("booking.title")}</h1>
        <button type="button" className="btn btn-small" onClick={() => void list.reload()} disabled={list.loading}>
          <Icon name="refresh" size={18} /> {t("common.refresh")}
        </button>
      </div>
      {justBooked && <Notice kind="ok">{t("booking.sent")}</Notice>}
      <ErrorBox error={list.error} />
      {list.loading && !list.data && <Loading />}
      {list.data && rows.length === 0 && (
        <Empty icon="calendar" text={isWorker ? t("booking.emptyWorker") : t("booking.emptyCustomer")}>
          {!isWorker && (
            <Link to="/c/find" className="btn btn-primary">
              {t("find.title")}
            </Link>
          )}
          {isWorker && (
            <Link to="/w/profile" className="btn">
              {t("nav.myProfile")}
            </Link>
          )}
        </Empty>
      )}
      {active.length > 0 && (
        <>
          <h2>{t("booking.active")}</h2>
          <ul className="plain stack">
            {active.map((b) => (
              <BookingCard key={b.id} b={b} onChange={replace} />
            ))}
          </ul>
        </>
      )}
      {past.length > 0 && (
        <>
          <h2>{t("booking.past")}</h2>
          <ul className="plain stack">
            {past.map((b) => (
              <BookingCard key={b.id} b={b} onChange={replace} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
