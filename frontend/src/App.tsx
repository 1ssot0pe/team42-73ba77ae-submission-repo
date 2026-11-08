/** Routes and app chrome: the glass nav, the page, and one quiet synthetic-data line in the footer. */
import { Navigate, Route, Routes } from "react-router-dom";
import { GlassNav } from "./components/shared";
import Home from "./pages/Home";
import Studio from "./pages/Studio";
import Trials from "./pages/Trials";
import Workspace from "./pages/Workspace";

export default function App() {
  return (
    <div className="app">
      <GlassNav />
      <main className="app__main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/trials" element={<Trials />} />
          <Route path="/trials/:projectId" element={<Workspace />} />
          <Route path="/trials/:projectId/:stage" element={<Workspace />} />
          {/* Legacy pages now live as stages inside a project workspace. */}
          <Route path="/predose" element={<Navigate to="/trials" replace />} />
          <Route path="/portal" element={<Navigate to="/trials" replace />} />
          <Route path="/dosing" element={<Navigate to="/trials" replace />} />
          <Route path="/postdose" element={<Navigate to="/trials" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="app__footer">
        <p>All trial data in Parallax is synthetic. No real patients.</p>
      </footer>
    </div>
  );
}
