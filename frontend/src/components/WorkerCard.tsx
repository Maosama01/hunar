// What a customer sees of a worker: the same card in search results, on the detail page and in the
// worker's own "what customers see" preview. Badges say exactly what was checked, by whom and when.
import type { Badge, PublicProfile } from "../api";
import { useI18n } from "../i18n";
import { endonym } from "../i18n/languages";
import { fmtDate } from "../util";
import { SampleBadge } from "./common";
import { Icon, TRADE_ICON } from "./Icon";
import { num, Stars } from "./ui";

export function BadgeChips({ p }: { p: PublicProfile }) {
  const { t } = useI18n();
  return (
    <div className="row wrap gap-s">
      {p.skill_assessed && (
        <span className="badge badge-skill">
          <Icon name="check" size={14} /> {t("badge.skill")}
        </span>
      )}
      {p.permit.status === "document_checked" && (
        <span className="badge badge-permit">
          <Icon name="idcard" size={14} /> {t("badge.permit")}
        </span>
      )}
      {p.permit.status === "self_declared" && <span className="badge">{t("badge.permitSelf")}</span>}
    </div>
  );
}

/** Each badge in plain words. */
export function BadgeExplain({ p }: { p: PublicProfile }) {
  const { t, lang } = useI18n();
  const line = (b: Badge) => {
    if (b.kind === "skill_assessed") {
      const q = b.qualification;
      return q
        ? t("badge.skillExplain", {
            date: fmtDate(b.date, lang),
            title: q.nsqf_level !== null ? `${q.title} (NSQF ${num(q.nsqf_level)})` : q.title,
          })
        : t("badge.skillExplainNoQp", { date: fmtDate(b.date, lang) });
    }
    return t("badge.permitExplain", { state: b.state || "?", date: fmtDate(b.date, lang) });
  };
  return (
    <ul className="plain stack-s">
      {p.badges.map((b, i) => (
        <li key={i} className={`badge-explain ${b.kind === "skill_assessed" ? "is-skill" : "is-permit"}`}>
          <Icon name={b.kind === "skill_assessed" ? "check" : "idcard"} size={20} />
          <span>{line(b)}</span>
        </li>
      ))}
      {p.permit.status === "self_declared" && (
        <li className="badge-explain">
          <Icon name="idcard" size={20} />
          <span>{t("badge.permitSelfExplain", { state: p.permit.state || "?" })}</span>
        </li>
      )}
      {p.badges.length === 0 && p.permit.status !== "self_declared" && (
        <li className="muted small">{t("badge.none")}</li>
      )}
    </ul>
  );
}

export function WorkerCard({ p, detailed = false }: { p: PublicProfile; detailed?: boolean }) {
  const { t, pick } = useI18n();
  return (
    <div className="worker-card">
      <div className="worker-head">
        <span className="avatar" aria-hidden="true">
          <Icon name={TRADE_ICON[p.trade] ?? "user"} size={26} />
        </span>
        <div className="grow">
          <div className="row wrap gap-s">
            <strong className="worker-name">{p.display_name}</strong>
            <SampleBadge show={p.is_sample} />
          </div>
          <div className="small muted">
            {pick(p.trade_name) || p.trade} · {t("worker.years", { n: p.years_experience })}
          </div>
        </div>
      </div>
      <div className="small row wrap gap-s">
        <span className="row gap-s">
          <Icon name="pin" size={16} />
          {[p.district, p.pincode_area].filter(Boolean).join(" · ")}
        </span>
        <Stars value={p.rating.average} count={p.rating.count} />
      </div>
      {p.languages.length > 0 && (
        <div className="small">
          {t("worker.speaks")}{" "}
          {p.languages.map((l, i) => (
            <span key={l} lang={l}>
              {i > 0 ? ", " : ""}
              {endonym(l)}
            </span>
          ))}
        </div>
      )}
      <BadgeChips p={p} />
      {detailed && p.bio && <p className="bio">{p.bio}</p>}
    </div>
  );
}
