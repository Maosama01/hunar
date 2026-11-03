import { useNavigate } from "react-router-dom";
import { LanguageGrid } from "../components/LanguageGrid";
import { Icon } from "../components/Icon";
import { TranslationBanner } from "../components/Layout";
import { useI18n } from "../i18n";
import { homePath, useSession } from "../session";

/** Change the app language (from the header globe button or Settings). */
export function LanguageScreen() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { account } = useSession();
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate(homePath(account)));
  return (
    <div className="onb">
      <TranslationBanner />
      <div className="onb-body stack">
        <div className="row between gap">
          <h1 className="h-inline">{t("onb.chooseLang")}</h1>
          <button type="button" className="btn" onClick={back}>
            <Icon name="chevron" className="flip" /> {t("common.done")}
          </button>
        </div>
        <p className="muted">{t("lang.deviceOnly")}</p>
        <LanguageGrid />
        <button type="button" className="btn btn-primary btn-block" onClick={back}>
          {t("common.done")}
        </button>
      </div>
    </div>
  );
}
