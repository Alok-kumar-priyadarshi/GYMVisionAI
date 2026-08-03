/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

/**
 * Vite configuration.
 *
 * The dev server proxies `/api` to the backend so the browser sees a single
 * origin. That keeps CORS behaviour the same in development as in production,
 * where both are served from one domain.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // Blank counts as unset, so an empty line in .env cannot break the proxy.
        target: process.env.VITE_API_PROXY_TARGET?.trim() || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
