/** React bindings for the projects store: re-read on every store change. */
import { useEffect, useState } from "react";
import { onProjectsChange, projects, type Project } from "../../store/projects";

export function useProjects(): Project[] {
  const [list, setList] = useState<Project[]>(() => projects.list());
  useEffect(() => {
    setList(projects.list());
    return onProjectsChange(() => setList(projects.list()));
  }, []);
  return list;
}

export function useProject(id: string | undefined): Project | null {
  const [p, setP] = useState<Project | null>(() => (id ? projects.get(id) : null));
  useEffect(() => {
    setP(id ? projects.get(id) : null);
    return onProjectsChange(() => setP(id ? projects.get(id) : null));
  }, [id]);
  return p;
}
