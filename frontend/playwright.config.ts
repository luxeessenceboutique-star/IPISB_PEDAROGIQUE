import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// frontend/package.json has "type": "module", so this file runs as ESM —
// no __dirname global available, derive it from import.meta.url instead.
const __dirname = fileURLToPath(new URL(".", import.meta.url));

/* ── Minimal .env.e2e loader — no `dotenv` dependency added just for this.
   Real credentials live in .env.e2e (gitignored, like every other .env in
   this repo); .env.e2e.example documents the shape. Existing process.env
   values always win, so CI secrets aren't shadowed by the file. ──────── */
function loadEnvFile(filePath: string) {
  if (!fs.existsSync(filePath)) return;
  for (const line of fs.readFileSync(filePath, "utf-8").split("\n")) {
    const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
    if (!match) continue;
    const key = match[1];
    if (key in process.env) continue;
    process.env[key] = (match[2] ?? "").trim().replace(/^["']|["']$/g, "");
  }
}
loadEnvFile(path.resolve(__dirname, ".env.e2e"));

const FRONTEND_URL = process.env.E2E_BASE_URL ?? "http://localhost:5178";
const BACKEND_URL = process.env.E2E_API_URL ?? "http://localhost:9000";
const isWindows = process.platform === "win32";

export default defineConfig({
  testDir: "./tests/e2e",
  // Generous: Vite's dev server compiles routes on first navigation, and
  // the very first test in a cold run can otherwise blow a tighter budget
  // through no fault of the test itself. Steady-state navigations are fast.
  timeout: 60_000,
  expect: { timeout: 8_000 },
  // The teaching-session/feedback specs share one E2E class+course fixture
  // and rely on start->end ordering within a single professor session —
  // running spec files in parallel workers risks two tests racing the same
  // "one active session" constraint. Keep it simple and serial.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL: FRONTEND_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: process.env.CI ? "off" : "retain-on-failure",
    actionTimeout: 10_000,
    // §21 — slow motion for headed demonstration runs, off by default so
    // normal/CI runs stay fast. Usage: E2E_SLOWMO=250 npm run test:e2e:headed
    launchOptions: {
      slowMo: process.env.E2E_SLOWMO ? Number(process.env.E2E_SLOWMO) : 0,
    },
  },

  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],

  // Reuses whatever's already running locally (both servers were already up
  // for this session) instead of double-starting; CI always starts fresh.
  webServer: [
    {
      command: "npm run dev",
      cwd: __dirname,
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: isWindows
        ? "venv\\Scripts\\python.exe -m uvicorn main:app --port 9000"
        : "venv/bin/python -m uvicorn main:app --port 9000",
      cwd: path.resolve(__dirname, "../backend"),
      url: `${BACKEND_URL}/docs`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
