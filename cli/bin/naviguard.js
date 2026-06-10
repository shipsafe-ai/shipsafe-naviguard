#!/usr/bin/env node
// ShipSafe NaviGuard CLI — uniform commands: init | demo | connect | health
const BASE = process.env.NAVIGUARD_API_URL || "https://naviguard-o34wppiwiq-uc.a.run.app";
const DASHBOARD = "https://naviguard-dashboard-336382452417.us-central1.run.app";
const NAME = "NaviGuard", PKG = "shipsafe-naviguard", PARTNER = "Arize Phoenix", SOURCE = "Phoenix project", SECRET = "PHOENIX_API_KEY";

const [, , cmd, ...args] = process.argv;
const flag = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function req(method, path, body, timeoutMs = 60000) {
  try {
    return await fetch(BASE + path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch { return null; }
}

const health = async () => {
  const r = await req("GET", "/health", null, 20000);
  if (!r) return console.error(`✗ cannot reach ${NAME} at ${BASE}`);
  const d = await r.json().catch(() => ({}));
  console.log(`✓ ${NAME} ${d.status ?? "ok"} — ${BASE}`);
};

const init = async () => {
  console.log(`\nShipSafe ${NAME} — powered by ${PARTNER}\n${"-".repeat(54)}`);
  console.log(`Agent URL : ${BASE}`);
  console.log(`Dashboard : ${DASHBOARD}`);
  console.log(`\nQuick start:`);
  console.log(`  npx ${PKG} demo               # run the demo (zero config, hosted)`);
  console.log(`  npx ${PKG} connect --uri ...  # point at your own ${SOURCE}`);
  console.log(`\nHealth check:`);
  await health();
};

const connect = async () => {
  const uri = flag("--uri");
  console.log(`\nConnect ${NAME} to your own ${SOURCE}:`);
  if (uri) console.log(`  target: ${uri}`);
  console.log(`  1. Store the connection in Secret Manager:`);
  console.log(`       gcloud secrets create ${SECRET} --data-file=-`);
  console.log(`  2. Deploy your own instance pointed at it (see terraform/ in the repo).`);
  console.log(`\n  No setup needed for the demo — it runs on the hosted instance with built-in fixtures:`);
  console.log(`       npx ${PKG} demo`);
};

const demo = async () => {
  console.log(`▶ Running Hormuz quality-regression demo on ${NAME} ...`);
  const r = await req("POST", "/run", { window_minutes: 60, scenario: "hormuz" }, 120000);
  if (!r) return console.error("✗ demo failed — cannot reach agent");
  if (!r.ok) return console.error(`✗ demo failed: HTTP ${r.status} ${(await r.text()).slice(0, 200)}`);
  const d = await r.json();
  console.log(`\n  Regression : ${d.regression_status}`);
  console.log(`  Root cause : ${d.root_cause ?? ""}`);
  console.log(`  Critic     : ${d.critic_verdict ?? ""}`);
  console.log(`  Status     : ${d.status}  — approve dataset + prompt in the dashboard:`);
  console.log(`               ${DASHBOARD}`);
};


const cmds = { init, demo, connect, health };
const fn = cmds[cmd];
if (!fn) {
  console.log("Usage: npx shipsafe-naviguard <init|demo|connect|health>");
  process.exit(1);
}
fn().catch((e) => { console.error(e.message); process.exit(1); });
