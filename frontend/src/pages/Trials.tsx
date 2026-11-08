/**
 * Trials (design v2): a quiet list of projects in hairline rows, or an empty state.
 * "Create a trial" is the one primary action and opens the create dialog.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { CreateTrialDialog } from "../components/projects/CreateTrialDialog";
import { ProjectStatusDot } from "../components/projects/StatusDot";
import { relativeDate } from "../components/projects/dates";
import { useProjects } from "../components/projects/useProjects";
import "../styles/home.css";

export default function Trials() {
  const list = useProjects();
  const [open, setOpen] = useState(false);

  return (
    <main className="page trials">
      <header className="trials__head">
        <h1 className="trials__title">Trials</h1>
        {list.length > 0 ? (
          <button type="button" className="btn btn--filled" onClick={() => setOpen(true)}>Create a trial</button>
        ) : null}
      </header>

      {list.length === 0 ? (
        <div className="trials__empty">
          <p>No trials yet. Start one from a blank page or an example.</p>
          <button type="button" className="btn btn--filled" onClick={() => setOpen(true)}>Create a trial</button>
        </div>
      ) : (
        <ul className="rows rows--table" aria-label="Your trials">
          <li className="rows__header" aria-hidden="true">
            <span>Name</span><span>Status</span><span>Last edited</span>
          </li>
          {list.map((p) => (
            <li key={p.id}>
              <Link className="rowlink rowlink--table" to={`/trials/${p.id}`}>
                <span className="rowlink__name">{p.name}</span>
                <ProjectStatusDot status={p.status} />
                <span className="rowlink__meta num">{relativeDate(p.updatedAt)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <CreateTrialDialog open={open} onClose={() => setOpen(false)} />
    </main>
  );
}
