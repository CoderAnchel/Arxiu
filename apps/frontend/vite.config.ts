import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true, // required for Docker volume mounts on macOS/Windows
    },
  },
  build: {
    outDir: "dist",
    sourcemap: mode !== "production",
    target: "es2022",
    cssCodeSplit: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests-setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      thresholds: {
        lines: 70,
        statements: 70,
        functions: 70,
        branches: 60,
      },
      exclude: ["**/*.gen.ts", "**/*.config.ts", "src/main.tsx", "e2e/**"],
    },
  },
}));
