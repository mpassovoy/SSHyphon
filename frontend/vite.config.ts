import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

const thisDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(thisDir, "..");
const versionFile = path.resolve(projectRoot, "VERSION");
const fallbackVersion = "0.0.0";
const appVersion = fs.existsSync(versionFile)
  ? fs.readFileSync(versionFile, "utf-8").trim() || fallbackVersion
  : fallbackVersion;

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts"
    },
    server: {
      port: Number(env.VITE_DEV_SERVER_PORT ?? 5173),
      proxy: {
        "/api": {
          target: env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true
        }
        ,
        "/icons": {
          target: env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true
        }
      }
    },
    build: {
      outDir: "dist",
      sourcemap: true
    },
    define: {
      __APP_VERSION__: JSON.stringify(appVersion),
      "import.meta.env.VITE_APP_VERSION": JSON.stringify(appVersion)
    }
  };
});
