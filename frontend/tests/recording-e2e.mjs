import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright-core";

const rootDir = fileURLToPath(new URL("../../", import.meta.url));
const frontendDir = fileURLToPath(new URL("../", import.meta.url));
const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8020);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? 5190);
const backendUrl = `http://127.0.0.1:${backendPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;

const browserCandidates = [
  process.env.E2E_BROWSER_PATH,
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
].filter(Boolean);

function browserPath() {
  const found = browserCandidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error("No Edge or Chrome executable found. Set E2E_BROWSER_PATH to run recording E2E.");
  }
  return found;
}

function spawnProcess(command, args, options) {
  const child = spawn(command, args, {
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
    ...options,
  });
  child.stdout.on("data", (chunk) => process.stdout.write(`[${options.name}] ${chunk}`));
  child.stderr.on("data", (chunk) => process.stderr.write(`[${options.name}] ${chunk}`));
  return child;
}

async function waitFor(url, label) {
  const started = Date.now();
  let lastError = "";
  while (Date.now() - started < 30000) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = `${response.status} ${response.statusText}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await delay(500);
  }
  throw new Error(`${label} did not become ready at ${url}. Last error: ${lastError}`);
}

async function stopProcess(child) {
  if (!child || child.killed || child.exitCode !== null) return;
  child.kill();
  await delay(500);
  if (child.exitCode === null) child.kill("SIGKILL");
}

async function main() {
  const backend = spawnProcess(
    "py",
    ["-3.13", "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", String(backendPort)],
    {
      cwd: rootDir,
      env: {
        ...process.env,
        ASR_PROVIDER: "",
        PRON_PROVIDER: "",
        LLM_ENABLE_REAL: "0",
      },
      name: "backend",
    },
  );
  const frontend = spawnProcess(
    process.execPath,
    ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", String(frontendPort), "--strictPort"],
    {
      cwd: frontendDir,
      env: { ...process.env, VITE_API_BASE: backendUrl },
      name: "frontend",
    },
  );

  let browser;
  try {
    await waitFor(`${backendUrl}/health`, "backend");
    await waitFor(frontendUrl, "frontend");

    browser = await chromium.launch({
      executablePath: browserPath(),
      headless: true,
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
      ],
    });
    const context = await browser.newContext({ permissions: ["microphone"] });
    const page = await context.newPage();
    await page.goto(frontendUrl);

    await page.getByRole("button", { name: "新建课程" }).click();
    await page.getByText("浏览器录音", { exact: false }).click();

    const recordingCards = page.locator(".recording-card");
    await expectCount(recordingCards, 2, "recording cards");
    await recordTrack(recordingCards.nth(0), "teacher");
    await recordTrack(recordingCards.nth(1), "student");

    await page.locator('input[type="checkbox"]').check();
    await page.getByRole("button", { name: "创建并开始分析" }).click();

    const backgroundCourse = page.locator(".course-card[data-job-id]").first();
    await backgroundCourse.waitFor({ timeout: 10000 });
    await page.waitForFunction(
      () => document.querySelector(".course-card[data-job-id] .course-status-badge.review_required") !== null,
      undefined,
      { timeout: 30000 },
    );
    await backgroundCourse.locator(".course-card-open-btn").click();
    await page.locator(".audio-ingest-panel").waitFor({ timeout: 10000 });

    const pageText = await page.locator("body").innerText();
    if (!pageText.includes("课堂录音") || !pageText.includes("老师音轨") || !pageText.includes("学生音轨")) {
      throw new Error("Workspace did not show expected audio ingest content after recording submit.");
    }
    console.log("recording e2e passed");
  } finally {
    if (browser) await browser.close();
    await stopProcess(frontend);
    await stopProcess(backend);
  }
}

async function expectCount(locator, expected, label) {
  const count = await locator.count();
  if (count !== expected) throw new Error(`Expected ${expected} ${label}, got ${count}.`);
}

async function recordTrack(card, label) {
  await card.getByRole("button", { name: "开始录音" }).click();
  await delay(1200);
  await card.getByRole("button", { name: "停止录音" }).click();
  await card.locator("audio").waitFor({ timeout: 10000 });
  const durationText = await card.innerText();
  if (!durationText.includes("录音时长")) {
    throw new Error(`No duration shown after recording ${label} track.`);
  }
}

await main();
