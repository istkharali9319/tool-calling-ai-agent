import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the Vite server forwards API calls to FastAPI, so no CORS setup is needed.
const API_TARGET = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": API_TARGET,
      "/health": API_TARGET,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
