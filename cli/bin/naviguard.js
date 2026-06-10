#!/usr/bin/env node
const [,, cmd, ...args] = process.argv;
const BASE = "https://naviguard-336382452417.us-central1.run.app";

const commands = {
  health: async () => {
    const r = await fetch(`${BASE}/health`).catch(() => null);
    if (!r) return console.error("✗ Cannot reach naviguard agent");
    const d = await r.json();
    console.log(`✓ naviguard ${d.status ?? "ok"} — ${BASE}`);
  },
  demo: async () => {
    console.log("▶ Running Hormuz Crisis demo on naviguard...");
    const r = await fetch(`${BASE}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: "hormuz" }),
    }).catch(() => null);
    if (!r) return console.error("✗ Demo failed — is naviguard agent running?");
    const d = await r.json();
    console.log(JSON.stringify(d, null, 2));
  },
  init: async () => {
    console.log(`
ShipSafe Naviguard — powered by Arize Phoenix
${"-".repeat(48)}
Agent URL : ${BASE}
Dashboard : https://naviguard-336382452417.us-central1.run.app

To connect to your own data:
  1. Set credentials in GCP Secret Manager (project: shipsafe-ai)
  2. Run: npx shipsafe-naviguard demo

Health check:`);
    await commands.health();
  },
};

const fn = commands[cmd];
if (!fn) {
  console.log("Usage: npx shipsafe-naviguard <init|demo|health>");
  process.exit(1);
}
fn().catch(e => { console.error(e.message); process.exit(1); });
