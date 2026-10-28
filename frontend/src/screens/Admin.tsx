import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, errorText, type AuditEntry, type VerifyResult } from "../api";
import { ErrorText, Notice, SampleBadge } from "../components/common";
import { useI18n } from "../i18n";
import { isConnected, useStatus } from "../status";
import { fmtTime } from "../util";

function prettyPayload(s: string): string {
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}

export function Admin() {
  const { t, lang } = useI18n();
  const connected = isConnected(useStatus());
  const [subjectInput, setSubjectInput] = useState("");
  const [subject, setSubject] = useState("");
  const [limit, setLimit] = useState(200);
  const [rows, setRows] = useState<AuditEntry[] | null>(null);
  const [sampleIds, setSampleIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRows(await api.audit({ limit, subject: subject || undefined }));
    } catch (e) {
      setError(errorText(e));
    }
  }, [limit, subject]);

  useEffect(() => {
    if (connected) void load();
  }, [connected, load]);

  // Sample workers/assessments, so their audit entries carry the SAMPLE DATA badge.
  useEffect(() => {
    if (!connected) return;
    void Promise.all([api.assessments(), api.workers()])
      .then(([as, ws]) => {
        setSampleIds(new Set([...as.filter((a) => a.is_sample).map((a) => a.id), ...ws.filter((w) => w.is_sample).map((w) => w.id)]));
      })
      .catch(() => undefined);
  }, [connected]);

  const runVerify = async () => {
    setVerifying(true);
    setError(null);
    try {
      setVerify(await api.auditVerify());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setVerifying(false);
    }
  };

  const apply = (e: FormEvent) => {
    e.preventDefault();
    setSubject(subjectInput.trim());
  };

  return (
    <div className="stack">
      <h1>{t("admin.title")}</h1>
      <p className="muted">{t("admin.note")}</p>
      {!connected && <Notice kind="warn">{t("common.needsConnection")}</Notice>}

      <section className="card stack-s">
        <button type="button" className="btn btn-primary" onClick={() => void runVerify()} disabled={!connected || verifying}>
          {verifying ? t("admin.verifying") : t("admin.verify")}
        </button>
        {verify && (
          <Notice kind={verify.ok ? "ok" : "error"} role="status">
            {verify.ok
              ? `✔ ${t("admin.verifyOk", { n: verify.entries, head: (verify.head ?? "").slice(0, 12) })}`
              : `✗ ${t("admin.verifyBad", { seq: verify.first_bad_seq ?? "?", n: verify.entries })}`}
          </Notice>
        )}
      </section>

      <form className="card stack-s" onSubmit={apply}>
        <label className="field">
          <span className="label">{t("admin.subject")}</span>
          <input type="text" value={subjectInput} onChange={(e) => setSubjectInput(e.target.value)} spellCheck={false} />
        </label>
        <label className="field">
          <span className="label">{t("admin.limit")}</span>
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[50, 200, 1000].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <div className="row gap">
          <button type="submit" className="btn" disabled={!connected}>
            {t("admin.apply")}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setSubjectInput("");
              setSubject("");
            }}
          >
            {t("admin.clear")}
          </button>
        </div>
      </form>

      <ErrorText error={error} />
      {rows && rows.length === 0 && <p className="muted">{t("admin.empty")}</p>}
      {rows && rows.length > 0 && (
        <div className="table-wrap" role="region" aria-label={t("admin.title")} tabIndex={0}>
          <table className="audit">
            <thead>
              <tr>
                <th scope="col">{t("admin.col.seq")}</th>
                <th scope="col">{t("admin.col.time")}</th>
                <th scope="col">{t("admin.col.actor")}</th>
                <th scope="col">{t("admin.col.action")}</th>
                <th scope="col">{t("admin.col.subject")}</th>
                <th scope="col">{t("admin.col.payload")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.seq}>
                  <td>{r.seq}</td>
                  <td className="nowrap">{fmtTime(r.ts, lang)}</td>
                  <td>{r.actor}</td>
                  <td>
                    <code>{r.action}</code>
                  </td>
                  <td>
                    <button type="button" className="link" onClick={() => { setSubjectInput(r.subject); setSubject(r.subject); }}>
                      {r.subject.length > 14 ? `${r.subject.slice(0, 13)}…` : r.subject}
                    </button>{" "}
                    <SampleBadge show={sampleIds.has(r.subject)} />
                  </td>
                  <td>
                    <details>
                      <summary>{t("admin.show")}</summary>
                      <pre className="payload">{prettyPayload(r.payload_json)}</pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
