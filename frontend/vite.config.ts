import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend. Override with VITE_API_TARGET (for example http://127.0.0.1:8001).
const target = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  // recharts makes the single bundle a little over 500 kB; that is fine for a local demo app.
  build: { chunkSizeWarningLimit: 900 },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target, changeOrigin: true } },
  },
});
