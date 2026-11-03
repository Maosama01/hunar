import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Notice, SampleBadge } from "../components/common";
import { Icon } from "../components/Icon";
import { Ltr } from "../components/ui";
import { useQueueCounts } from "../data";
import { useI18n, type Key } from "../i18n";
import { endonym } from "../i18n/languages";
import { clearSession, isStaff, useSession } from "../session";

export function Settings() {
  const { t, lang } = useI18n();
  const { account } = useSession();
  const counts = useQueueCounts();
  const [busy, setBusy] = useState(false);
  if (!account) return null;
  const staff = isStaff(account);
  const queued = counts?.ops ?? 0;

  const logout = async () => {
    setBusy(true);
    try {
      await api.logout();
    } catch {
      /* offline: the token is dropped on this device anyway */
    }
    clearSession("logout", staff ? "/login?staff=1" : "/welcome?step=role"); // the route guard goes there
  };

  const privacy = account.role === "worker" ? "/w/privacy" : account.role === "customer" ? "/c/privacy" : null;

  return (
    <div className="stack">
      <h1>{t("settings.title")}</h1>
      <section className="card stack-s">
        <div className="row wrap gap-s">
          <strong className="big-name">{account.display_name}</strong>
          <SampleBadge show={account.is_sample} />
        </div>
        <p className="muted">
          {t(`roles.${account.role}` as Key)} · <Ltr>{account.phone_masked}</Ltr>
        </p>
      </section>

      <nav className="card menu" aria-label={t("settings.title")}>
        <Link to="/language" className="menu-item">
          <Icon name="globe" />
          <span className="grow">{t("settings.language")}</span>
          <span className="muted" lang={lang}>
            {endonym(lang)}
          </span>
          <Icon name="chevron" className="flip-rtl" size={18} />
        </Link>
        {(account.role === "worker" || account.role === "customer") && (
          <Link to={`/welcome?step=intro&role=${account.role}&replay=1`} className="menu-item">
            <Icon name="book" />
            <span className="grow">{t("settings.howItWorks")}</span>
            <Icon name="chevron" className="flip-rtl" size={18} />
          </Link>
        )}
        {privacy && (
          <Link to={privacy} className="menu-item">
            <Icon name="shield" />
            <span className="grow">{t("nav.privacy")}</span>
            <Icon name="chevron" className="flip-rtl" size={18} />
          </Link>
        )}
        {staff && (
          <>
            <Link to="/queue" className="menu-item">
              <Icon name="refresh" />
              <span className="grow">{t("queue.title")}</span>
              <Icon name="chevron" className="flip-rtl" size={18} />
            </Link>
            <Link to="/rater" className="menu-item">
              <Icon name="users" />
              <span className="grow">{t("home.openRater")}</span>
              <Icon name="chevron" className="flip-rtl" size={18} />
            </Link>
          </>
        )}
      </nav>

      <section className="card stack-s">
        {staff && queued > 0 && <Notice kind="warn">{t("settings.queuedOnLogout", { n: queued })}</Notice>}
        <button type="button" className="btn btn-block btn-danger-outline" onClick={() => void logout()} disabled={busy}>
          <Icon name="logout" /> {t("settings.logout")}
        </button>
        <p className="hint">{t("settings.logoutNote")}</p>
      </section>
    </div>
  );
}
