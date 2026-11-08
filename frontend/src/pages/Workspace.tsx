/**
 * Project workspace (design v2): /trials/:projectId/:stage?
 * Main column plus the vertical stepper on the right. The Draft stage is a document editor; later stages
 * render the existing pages against this project's trial (set through useTrial().setTrialId).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { VerticalStepper } from "../components/stepper/VerticalStepper";
import { currentStageIndex, deriveStages, isStageId, STAGES, type StageId } from "../components/stepper/stages";
import { DraftEditor } from "../components/projects/DraftEditor";
import { ReportPanel } from "../components/projects/ReportPanel";
import { ProjectStatusDot } from "../components/projects/StatusDot";
import { TrialClock } from "../components/projects/TrialClock";
import { useProject } from "../components/projects/useProjects";
import { projects, type Project } from "../store/projects";
import { TrialProvider, useTrial } from "../trial";
import { TrialBridge } from "../trialBridge";
import ModulePage from "./ModulePage";
import Portal from "./Portal";
import Predose from "./Predose";
import "../styles/home.css";
import "../styles/workspace.css";

function StageBody({ stage }: { stage: StageId }) {
  const { state } = useTrial();
  switch (stage) {
    case "design-review":
      return <Predose only="design" />;
    case "recruitment":
      return <Predose only="recruitment" />;
    case "screening":
      return (
        <>
          <Predose only="screening" />
          <Portal />
        </>
      );
    case "dosing":
      return <ModulePage key="dosing" module="dosing" />;
    case "follow-up":
      return <ModulePage key="postdose" module="postdose" />;
    case "report":
      return state ? <ReportPanel state={state} /> : <p className="ws-quiet">Loading the trial.</p>;
    default:
      return null;
  }
}

export default function Workspace() {
  const { projectId } = useParams<{ projectId: string; stage?: string }>();
  const navigate = useNavigate();
  const project = useProject(projectId);
  // True when the TrialProvider has replaced the workspace with TrialLost (see trialBridge.tsx).
  const [lost, setLost] = useState(false);
  const onGone = useCallback((gone: boolean) => setLost(gone), []);

  if (!project) {
    return (
      <main className="page ws-missing">
        <p className="ws-quiet">This trial could not be found on this device.</p>
        <Link className="textbtn" to="/trials">Back to trials</Link>
      </main>
    );
  }

  const relaunch = () => {
    projects.update(project.id, { trialId: null, status: "draft" });
    navigate(`/trials/${project.id}/draft`);
  };

  // One provider per project and trial: switching either starts from a clean trial context.
  return (
    <>
      <TrialProvider key={`${project.id}:${project.trialId ?? "draft"}`}>
        <TrialBridge onGone={onGone} />
        <WorkspaceInner project={project} />
      </TrialProvider>
      {lost ? (
        <p className="page ws-lost-note">
          Your protocol draft for {project.name} is safe.{" "}
          <button type="button" className="textbtn" onClick={relaunch}>Open the draft to launch it again</button>
        </p>
      ) : null}
    </>
  );
}

function WorkspaceInner({ project }: { project: Project }) {
  const { stage: stageParam } = useParams<{ projectId: string; stage?: string }>();
  const navigate = useNavigate();
  const { trialId, state, setTrialId, error } = useTrial();

  const projectTrial = project.trialId ?? null;

  // Point the shared trial context at this project's trial.
  useEffect(() => {
    if (projectTrial !== trialId) setTrialId(projectTrial);
    // Only react to the project's trial changing, not to every context update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, projectTrial]);

  const ours = !!projectTrial && projectTrial === trialId ? state : null;
  const launched = !!projectTrial;
  const stages = useMemo(() => deriveStages(launched, ours), [launched, ours]);

  // Mark the project complete once its trial is closed.
  useEffect(() => {
    if (!ours) return;
    if (ours.phase === "closed" && project.status !== "complete") projects.update(project.id, { status: "complete" });
  }, [project, ours]);

  const curIdx = Math.min(currentStageIndex(launched, ours), STAGES.length - 1);
  const current = STAGES[curIdx].id;
  if (!isStageId(stageParam)) {
    return <Navigate to={`/trials/${project.id}/${current}`} replace />;
  }
  const stage: StageId = stageParam;
  const stageLabel = STAGES.find((s) => s.id === stage)?.label ?? "";
  const lost = launched && error && !ours;

  return (
    <div className="page ws">
      <div className="ws__grid">
        <div className="ws__main">
          <header className="ws__head">
            <p className="ws__crumb"><Link to="/trials">Trials</Link> <span aria-hidden="true">/</span> {stageLabel}</p>
            <h1 className="ws__title">{project.name}</h1>
            <p className="ws__meta">
              <ProjectStatusDot status={project.status} />
              {ours && ours.day >= 1 ? <span className="num">Day {ours.day} of {ours.close_day}</span> : null}
              {ours && ours.day < 1 ? <span>Setup</span> : null}
            </p>
            {ours && stage !== "draft" ? <TrialClock state={ours} /> : null}
            {lost ? <p className="ws-quiet ws-quiet--watch">The trial server is not reachable: {error}</p> : null}
          </header>

          <div className="ws__body">
            {stage === "draft" ? (
              <DraftEditor project={project} />
            ) : !launched ? (
              <p className="ws-quiet">Launch the trial to start this stage.</p>
            ) : projectTrial !== trialId ? (
              <p className="ws-quiet">Opening the trial.</p>
            ) : (
              <StageBody stage={stage} />
            )}
          </div>
        </div>

        <aside className="ws__stepper" aria-label="Stages">
          <VerticalStepper stages={stages} activeId={stage} onSelect={(id) => navigate(`/trials/${project.id}/${id}`)} />
        </aside>
      </div>
    </div>
  );
}
