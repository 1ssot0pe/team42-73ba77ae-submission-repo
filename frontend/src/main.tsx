import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
// Shared styles first, so page stylesheets (imported by the pages via App) come later and win ties.
import "./styles/tokens.css";
import "./styles/glass.css";
import "./styles/base.css";
import "./styles/components.css";
import App from "./App";
import { ToastProvider, applyTheme, getThemePref } from "./components/shared";

applyTheme(getThemePref());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ToastProvider>
        {/* The TrialProvider lives inside the project workspace (pages/Workspace.tsx). */}
        <App />
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
