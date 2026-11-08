/** Routes and app chrome: specimen field, floating glass nav, then the page. */
import { Navigate, Route, Routes } from "react-router-dom";
import { SpecimenField } from "./components/SpecimenField";
import { GlassNav } from "./components/shared";
import MissionControl from "./pages/MissionControl";
import ModulePage from "./pages/ModulePage";
import Portal from "./pages/Portal";
import Predose from "./pages/Predose";

export default function App() {
  return (
    <div className="app">
      <SpecimenField />
      <GlassNav />
      <Routes>
        <Route path="/" element={<MissionControl />} />
        <Route path="/predose" element={<Predose />} />
        <Route path="/portal" element={<Portal />} />
        <Route path="/dosing" element={<ModulePage key="dosing" module="dosing" />} />
        <Route path="/postdose" element={<ModulePage key="postdose" module="postdose" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
