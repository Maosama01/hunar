import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api, type AccountRole, type OpKind } from "../api";
import { refreshAssessmentList, useBlockingOp, useQueueCounts } from "../data";
import { enText, useI18n, type Key } from "../i18n";
import { endonym } from "../i18n/languages";
import { homePath, isStaff, quizPending, useSession } from "../session";
import { useStatus } from "../status";
import { discardOp, retryOp, syncNow } from "../sync";
import { fmtTime } from "../util";
import { Icon, type IconName } from "./Icon";
import { OfflineNotice } from "./ui";

export const kindKey = (k: OpKind) => `kind.${k}` as Key;

function ConnBadge({ quietWhenOnline = false }: { quietWhenOnline?: boolean }) {
  const { t } = useI18n();
  const status = useStatus();
  const badge = !status.online
    ? { cls: "off", text: t("header.offline") }
    : status.reachable === false
      ? { cls: "warn", text: t("header.unreachable") }
      : { cls: "on", text: t("header.online") };
  if (quietWhenOnline && badge.cls === "on") return null;
  return (
    <span className={`conn conn-${badge.cls}`} role="status" aria-live="polite">
      <span className="dot" aria-hidden="true" />
      {badge.text}
    </span>
  );
}

function LangButton() {
  const { t, lang } = useI18n();
  return (
    <Link to="/language" className="btn btn-small lang-btn" aria-label={t("header.changeLang")}>
      <Icon name="globe" size={18} />
      <span lang={lang}>{endonym(lang)}</span>
    </Link>
  );
}

function SettingsButton() {
  const { t } = useI18n();
  const { account } = useSession();
  if (!account) return null;
  return (
    <Link to="/settings" className="btn btn-small icon-btn" aria-label={t("nav.settings")} title={t("nav.settings")}>
      <Icon name="settings" size={20} />
    </Link>
  );
}

function Brand() {
  const { t } = useI18n();
  const { account } = useSession();
  return (
    <Link to={homePath(account)} className="brand" aria-label={t("header.home")}>
      <img src="/mark-white.svg" alt="" width={26} height={26} />
      <span>{t("app.name")}</span>
    </Link>
  );
}

function PublicHeader() {
  return (
    <header className="app-header">
      <div className="header-row">
        <Brand />
        <ConnBadge quietWhenOnline />
        <LangButton />
        <SettingsButton />
      </div>
    </header>
  );
}

function StaffHeader() {
  const { t, lang } = useI18n();
  const status = useStatus();
  const counts = useQueueCounts();
  const { account } = useSession();
  const queued = (counts?.ops ?? 0) + (counts?.ratings ?? 0);

  const manualSync = async () => {
    await syncNow();
    try {
      await api.health();
      await refreshAssessmentList();
    } catch {
      /* the badge shows the problem */
    }
  };

  return (
    <header className="app-header">
      <div className="header-row">
        <Brand />
        <ConnBadge />
        <LangButton />
        <SettingsButton />
      </div>
      {/* The strip only grows when something needs attention: queued changes, a sync in progress or a
          server that cannot be reached. With nothing waiting it just says who is signed in. */}
      <div className="header-row header-sub">
        {(queued > 0 || status.syncing) && (
          <Link to="/queue" className={`queue-chip ${queued ? "has" : ""}`} aria-label={t("header.queuedAria", { n: queued })}>
            <Icon name="refresh" size={16} /> {t("header.queued", { n: queued })}
          </Link>
        )}
        {(queued > 0 || status.syncing || status.reachable === false) && (
          <button
            type="button"
            className="btn btn-small"
            onClick={() => void manualSync()}
            disabled={status.syncing || !status.online}
          >
            {status.syncing ? t("header.syncing") : t("header.syncNow")}
          </button>
        )}
        {account && (
          <span className="who" title={status.lastSyncAt ? t("header.lastSync", { time: fmtTime(status.lastSyncAt, lang) }) : undefined}>
            {account.display_name} · {t(`roles.${account.role}` as Key)}
          </span>
        )}
      </div>
    </header>
  );
}

/** Shown when the first queued op was refused: later ops wait until it is retried or discarded. */
function BlockingBanner() {
  const { t } = useI18n();
  const op = useBlockingOp();
  const [confirming, setConfirming] = useState(false);
  if (!op) return null;
  return (
    <div className="blocking" role="alert">
      <p>
        <strong>{t("banner.rejected", { kind: t(kindKey(op.kind)), error: op.error ?? "" })}</strong>
      </p>
      <p className="small">{t("banner.rejectedHelp")}</p>
      <div className="row gap">
        <button type="button" className="btn" onClick={() => void retryOp(op.seq!)}>
          {t("banner.retry")}
        </button>
        {!confirming ? (
          <button type="button" className="btn btn-danger-outline" onClick={() => setConfirming(true)}>
            {t("banner.discard")}
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => {
                setConfirming(false);
                void discardOp(op.seq!);
              }}
            >
              {t("banner.discardConfirm")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setConfirming(false)}>
              {t("banner.cancel")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/** "Not all text is translated" / "Machine-translated" notes for the chosen language. */
export function TranslationBanner() {
  const { t, lang, coverage, loading } = useI18n();
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  if (lang === "en" || loading || closed[lang]) return null;
  const incomplete = !coverage.exists || coverage.share < 0.999;
  const machine = coverage.meta?.reviewed === false;
  if (!incomplete && !machine) return null;
  return (
    <div className="tr-banner" role="note">
      <div className="tr-banner-inner">
        <Icon name="globe" size={18} />
        <div className="grow">
          {incomplete && <p>{t("i18n.incomplete", { lang: endonym(lang) })}</p>}
          {machine && <p>{t("i18n.machine")}</p>}
        </div>
        <button type="button" className="btn btn-small btn-ghost" onClick={() => setClosed((c) => ({ ...c, [lang]: true }))}>
          {t("common.close")}
        </button>
      </div>
    </div>
  );
}

interface NavItem {
  to: string;
  icon: IconName;
  label: Key;
}

function navFor(role: AccountRole | null, quizFirst = false): NavItem[] {
  switch (role) {
    case "worker":
      if (quizFirst)
        return [
          { to: "/w/quiz", icon: "quiz", label: "nav.quiz" },
          { to: "/w/privacy", icon: "shield", label: "nav.privacy" },
        ];
      return [
        { to: "/w/quiz", icon: "quiz", label: "nav.quiz" },
        { to: "/w/profile", icon: "user", label: "nav.myProfile" },
        { to: "/w/assess", icon: "clipboard", label: "nav.assess" },
        { to: "/w/bookings", icon: "calendar", label: "nav.bookings" },
        { to: "/w/privacy", icon: "shield", label: "nav.privacy" },
      ];
    case "customer":
      return [
        { to: "/c/find", icon: "search", label: "nav.find" },
        { to: "/c/bookings", icon: "calendar", label: "nav.bookings" },
        { to: "/c/privacy", icon: "shield", label: "nav.privacy" },
      ];
    case "facilitator":
      return [
        { to: "/staff", icon: "home", label: "nav.staffHome" },
        { to: "/declare", icon: "plus", label: "nav.newDeclaration" },
        { to: "/queue", icon: "refresh", label: "nav.queue" },
      ];
    case "assessor":
      return [
        { to: "/staff", icon: "home", label: "nav.staffHome" },
        { to: "/staff/requests", icon: "inbox", label: "nav.requests" },
        { to: "/admin", icon: "file", label: "nav.audit" },
        { to: "/queue", icon: "refresh", label: "nav.queue" },
      ];
    case "admin":
      return [
        { to: "/staff", icon: "home", label: "nav.staffHome" },
        { to: "/staff/requests", icon: "inbox", label: "nav.requests" },
        { to: "/staff/permits", icon: "idcard", label: "nav.permits" },
        { to: "/admin", icon: "file", label: "nav.audit" },
      ];
    default:
      return [
        { to: "/c/find", icon: "search", label: "nav.find" },
        { to: "/welcome", icon: "home", label: "nav.start" },
        { to: "/login", icon: "user", label: "nav.login" },
      ];
  }
}

function BottomBar() {
  const { t, lang, has } = useI18n();
  const { account } = useSession();
  const items = navFor(account?.role ?? null, quizPending(account));
  return (
    <div className="bottom">
      <p className="principle" role="note">
        <strong>{t("principle")}</strong>
        {lang !== "en" && has("principle") && <span lang="en"> · {enText("principle")}</span>}
      </p>
      <nav className="bottom-nav" aria-label={t("nav.main")} style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} end={it.to === "/staff"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <Icon name={it.icon} size={24} />
            <span className="nav-label">{t(it.label)}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

export function Layout() {
  const { t } = useI18n();
  const { account } = useSession();
  const staff = isStaff(account);
  return (
    <div className={`app ${staff ? "is-staff" : "is-public"}`}>
      <a href="#main" className="skip">
        {t("common.skip")}
      </a>
      {staff ? <StaffHeader /> : <PublicHeader />}
      {staff && <BlockingBanner />}
      <TranslationBanner />
      <main id="main" className="main">
        {!staff && <OfflineNotice />}
        <Outlet />
      </main>
      <BottomBar />
    </div>
  );
}
