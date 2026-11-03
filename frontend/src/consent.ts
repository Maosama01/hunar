// Consent purposes come from the server (backend/hunar/accounts/notice.py). Their English text is the
// legal source; a translation is used only when it was made for the same notice version.
import type { AuthConfig, Purpose } from "./api";
import { isKey, useI18n, type Key } from "./i18n";

export interface PurposeText {
  title: string;
  why: string;
  data: string;
  withdraw: string;
  /** Language of why/data/withdraw (English when no matching translation exists). */
  lang: string;
}

export function usePurposeText(cfg: AuthConfig | undefined): (purpose: string, spec: Purpose) => PurposeText {
  const { t, lang, has } = useI18n();
  const versionOk = !!cfg && t("consent.translatedNotice") === cfg.notice_version;
  return (purpose, spec) => {
    const k = (f: string) => `consent.p.${purpose}.${f}`;
    const tk = (f: string) => (isKey(k(f)) ? (k(f) as Key) : null);
    const why = tk("why");
    const useT = lang !== "en" && versionOk && why !== null && has(why);
    const title = tk("title");
    return {
      title: title ? t(title) : purpose,
      why: useT ? t(why!) : spec.why,
      data: useT && tk("data") ? t(tk("data")!) : spec.data.join(", "),
      withdraw: useT && tk("withdraw") ? t(tk("withdraw")!) : spec.withdraw,
      lang: useT ? lang : "en",
    };
  };
}

/** Required purposes first, then optional ones, keeping the server's order within each group. */
export function orderedPurposes(purposes: Record<string, Purpose> | undefined): [string, Purpose][] {
  const all = Object.entries(purposes ?? {});
  return [...all.filter(([, p]) => p.required), ...all.filter(([, p]) => !p.required)];
}
