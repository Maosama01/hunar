import { setTick } from "../actions";
import type { Task } from "../api";
import { Loading, PresenceNote } from "../components/common";
import { GuidedClips } from "../components/GuidedClips";
import { PhotoSlot } from "../components/PhotoSlot";
import { tradeTasks, useRubrics, type AssessmentView } from "../data";
import { useI18n } from "../i18n";
import { actorName, useSettings } from "../settings";
import { useAssessmentCtx } from "./AssessmentLayout";

function TaskCard({ task, view, open }: { task: Task; view: AssessmentView; open: boolean }) {
  const { t, pick } = useI18n();
  const settings = useSettings();
  const actor = actorName(settings);
  const ticks = view.checklist[task.task_id] ?? {};
  const answered = task.checklist.filter((c) => c.id in ticks).length;
  const evidence = view.evidence.filter((e) => e.task_id === task.task_id);
  const frozen = view.signedOff;

  return (
    <details className="card task" open={open}>
      <summary>
        <div className="grow">
          <strong>{pick(task.title)}</strong>
          <div className="small muted">
            {t("tasks.answered", { a: answered, t: task.checklist.length })} ·{" "}
            {t("tasks.photoCount", { n: evidence.length })}
          </div>
        </div>
      </summary>
      <p>{pick(task.instructions)}</p>
      {task.review && <p className="fine-print">{pick(task.review)}</p>}

      <h3>{t("tasks.checklist")}</h3>
      <ul className="plain checklist">
        {task.checklist.map((item) => {
          const value = ticks[item.id];
          const pending = view.checklistPending.has(`${task.task_id}|${item.id}`);
          const name = `${task.task_id}-${item.id}`;
          return (
            <li key={item.id} className="check-item">
              <div className="check-label" id={`${name}-l`}>
                {pick(item)}
                {pending && <span className="dot-pending" title={t("common.pending")} aria-label={t("common.pending")} />}
              </div>
              <div className="yesno" role="group" aria-labelledby={`${name}-l`}>
                <button
                  type="button"
                  className={`yn yes ${value === true ? "on" : ""}`}
                  aria-pressed={value === true}
                  disabled={frozen}
                  onClick={() => void setTick(view.id, task.task_id, item.id, true, actor)}
                >
                  ✓ {t("tasks.observed")}
                </button>
                <button
                  type="button"
                  className={`yn no ${value === false ? "on" : ""}`}
                  aria-pressed={value === false}
                  disabled={frozen}
                  onClick={() => void setTick(view.id, task.task_id, item.id, false, actor)}
                >
                  ✗ {t("tasks.notObserved")}
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      <GuidedClips task={task} view={view} />

      <h3>{t("tasks.photos")}</h3>
      <div className="stack-s">
        {task.photos.map((spec) => (
          <PhotoSlot
            key={spec.id}
            assessmentId={view.id}
            taskId={task.task_id}
            spec={spec}
            evidence={evidence.filter((e) => e.photo_id === spec.id)}
            actor={actor}
            disabled={frozen}
          />
        ))}
      </div>
    </details>
  );
}

export function Tasks() {
  const { t } = useI18n();
  const { view } = useAssessmentCtx();
  const rubrics = useRubrics();

  return (
    <div className="stack">
      <h2>{t("tasks.title")}</h2>
      <p className="muted">{t("tasks.intro")}</p>
      <PresenceNote />
      {rubrics === undefined && <Loading />}
      {rubrics === null && <p className="muted">{t("common.needsConnection")}</p>}
      {rubrics && tradeTasks(rubrics, view.trade).map((task, i) => <TaskCard key={task.task_id} task={task} view={view} open={i === 0} />)}
    </div>
  );
}
