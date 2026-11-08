/**
 * Home (design v2): headline, one sentence, two doors (Evidence studio, Trials), then recent work.
 * Recent analyses are read defensively from localStorage ("parallax.analyses.v1", written by the studio).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useProjects } from "../components/projects/useProjects";
import { ProjectStatusDot } from "../components/projects/StatusDot";
import { relativeDate } from "../components/projects/dates";
import "../styles/home.css";

interface RecentAnalysis {
  id: string;
  input: string;
  title?: string;
  createdAt: string;
}

function readAnalyses(): RecentAnalysis[] {
  try {
    const raw = localStorage.getItem("parallax.analyses.v1");
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((a): a is RecentAnalysis => !!a && typeof a === "object" && typeof (a as RecentAnalysis).id === "string")
      .map((a) => ({ id: a.id, input: String(a.input ?? ""), title: typeof a.title === "string" ? a.title : undefined, createdAt: String(a.createdAt ?? "") }))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, 5);
  } catch {
    return [];
  }
}

function useAnalyses(): RecentAnalysis[] {
  const [list, setList] = useState<RecentAnalysis[]>(readAnalyses);
  useEffect(() => {
    const update = () => setList(readAnalyses());
    window.addEventListener("storage", update);
    window.addEventListener("parallax:analyses", update);
    return () => {
      window.removeEventListener("storage", update);
      window.removeEventListener("parallax:analyses", update);
    };
  }, []);
  return list;
}

function Door({ to, title, line }: { to: string; title: string; line: string }) {
  return (
    <Link to={to} className="door">
      <span className="door__title">{title}</span>
      <span className="door__line">{line}</span>
      <span className="door__arrow" aria-hidden="true">→</span>
    </Link>
  );
}

export default function Home() {
  const recentProjects = useProjects().slice(0, 5);
  const analyses = useAnalyses();
  const hasRecent = recentProjects.length > 0 || analyses.length > 0;

  return (
    <main className="page home">
      <header className="home__head">
        <h1 className="home__title">Run psychedelic trials that stay honest about blinding.</h1>
        <p className="home__lede">
          Parallax checks published trials for functional unblinding, and runs new ones end to end with agents that
          keep the blind in view from protocol to report.
        </p>
      </header>

      <nav className="doors" aria-label="Start">
        <Door to="/studio" title="Evidence studio" line="Check a published trial" />
        <Door to="/trials" title="Trials" line="Run a trial end to end" />
      </nav>

      {hasRecent ? (
        <section className="home__recent" aria-labelledby="home-recent">
          <h2 id="home-recent" className="home__h2">Recent</h2>
          {recentProjects.length > 0 ? (
            <div className="recent">
              <h3 className="recent__label">Trials</h3>
              <ul className="rows">
                {recentProjects.map((p) => (
                  <li key={p.id}>
                    <Link className="rowlink" to={`/trials/${p.id}`}>
                      <span className="rowlink__name">{p.name}</span>
                      <ProjectStatusDot status={p.status} />
                      <span className="rowlink__meta num">{relativeDate(p.updatedAt)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {analyses.length > 0 ? (
            <div className="recent">
              <h3 className="recent__label">Analyses</h3>
              <ul className="rows">
                {analyses.map((a) => (
                  <li key={a.id}>
                    <Link className="rowlink" to={`/studio?a=${encodeURIComponent(a.id)}`}>
                      <span className="rowlink__name">{a.title || a.input || "Untitled analysis"}</span>
                      <span className="rowlink__meta num">{a.createdAt ? relativeDate(a.createdAt) : ""}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
