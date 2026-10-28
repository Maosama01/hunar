import { useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { api, type OpKind } from "../api";
import { refreshAssessmentList, useBlockingOp, useQueueCounts } from "../data";
import { dicts, useI18n, type Key } from "../i18n";
import { useSettings } from "../settings";
import { isConnected, useStatus } from "../status";
import { discardOp, retryOp, syncNow } from "../sync";
import { fmtTime } from "../util";

export const kindKey = (k: OpKind) => `kind.${k}` as Key;

function Header() {
  const { t, lang, setLang } = useI18n();
  const status = useStatus();
  const counts = useQueueCounts();
  const { role, actor } = useSettings();
  const connected = isConnected(status);
  const queued = (counts?.ops ?? 0) + (counts?.ratings ?? 0);

  const badge = !status.online
    ? { cls: "off", text: t("header.offline") }
    : status.reachable === false
      ? { cls: "warn", text: t("header.unreachable") }
      : { cls: "on", text: t("header.online") };

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
        <Link to="/" className="brand" aria-label={t("header.home")}>
          <img src="/icon.svg" alt="" width={28} height={28} />
          <span>{t("app.name")}</span>
        </Link>
        <span className={`conn conn-${badge.cls}`} role="status" aria-live="polite">
          <span className="dot" aria-hidden="true" />
          {badge.text}
        </span>
        <button
          type="button"
          className="btn btn-small btn-ghost lang-toggle"
          onClick={() => setLang(lang === "en" ? "hi" : "en")}
          aria-label={t("header.switchLangAria")}
          lang={lang === "en" ? "hi" : "en"}
        >
          {t("header.switchLang")}
        </button>
      </div>
      <div className="header-row header-sub">
        <Link to="/queue" className={`queue-chip ${queued ? "has" : ""}`} aria-label={t("header.queuedAria", { n: queued })}>
          ⇅ {t("header.queued", { n: queued })}
        </Link>
        <button
          type="button"
          className="btn btn-small"
          onClick={() => void manualSync()}
          disabled={status.syncing || !status.online}
        >
          {status.syncing ? t("header.syncing") : t("header.syncNow")}
        </button>
        {role && (
          <span className="who" title={status.lastSyncAt ? t("header.lastSync", { time: fmtTime(status.lastSyncAt, lang) }) : undefined}>
            {t(`roles.${role}` as Key)}
            {actor.trim() ? ` · ${actor.trim()}` : ""}
          </span>
        )}
        {!connected && <span className="sr-only">{t("common.needsConnection")}</span>}
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

function Footer() {
  const { lang } = useI18n();
  const other = lang === "en" ? "hi" : "en";
  return (
    <footer className="principle" role="note">
      <strong>{dicts[lang].principle}</strong>
      <span lang={other}> · {dicts[other].principle}</span>
    </footer>
  );
}

export function Layout() {
  return (
    <div className="app">
      <a href="#main" className="skip">
        Skip to content
      </a>
      <Header />
      <BlockingBanner />
      <main id="main" className="main">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
