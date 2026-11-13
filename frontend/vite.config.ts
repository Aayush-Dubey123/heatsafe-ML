import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Local development serves on :3000, the origin the API allows by default (HEATSAFE_CORS_ORIGINS).
export default defineConfig({
  plugins: [react()],
  server: { port: 3000, strictPort: true },
  // MapLibre starts its own web worker; pre-bundling breaks the worker URL in dev.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  build: {
    target: "es2022",
    sourcemap: false,
    rollupOptions: {
      output: { manualChunks: { maplibre: ["maplibre-gl"] } },
    },
    // The map library is its own lazy chunk; the app budget is enforced by scripts/check-bundle.mjs.
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup/setup.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
