import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE is "/dwarpal/" for GitHub Pages and "/" everywhere else.
// In development the API runs on :8000; Vite forwards /api to it.
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
