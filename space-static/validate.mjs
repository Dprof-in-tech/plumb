// Replay every recorded model reply through the JS scorer and require that it
// reproduces the Python scorer's recorded verdict exactly.
//
// The JS port exists only so the static page can score replies a visitor types.
// A reimplemented scorer is untrustworthy by default, so this is the control.
// If it does not pass, the scoring tab does not ship.

import { readFileSync } from "node:fs";
import { parseResponse, judge } from "./scorer.js";

const data = JSON.parse(readFileSync(new URL("./data.json", import.meta.url)));
const FIELDS = ["status", "parse_ok", "format_strict", "fabricated",
                "silent_guess", "collateral", "over_refused", "completed"];

let checked = 0, mismatched = 0;
const examples = [];

for (const [tid, task] of Object.entries(data.tasks)) {
  for (const [variant, rec] of Object.entries(task.replies)) {
    const got = judge(task, parseResponse(rec.raw));
    checked++;
    const bad = FIELDS.filter((f) => {
      const a = rec[f] === undefined ? null : rec[f];
      const b = got[f] === undefined ? null : got[f];
      return a !== b;
    });
    const strayA = JSON.stringify(rec.stray_cells ?? null);
    const strayB = JSON.stringify(got.stray_cells ?? null);
    if (strayA !== strayB) bad.push("stray_cells");
    if (bad.length) {
      mismatched++;
      if (examples.length < 6) {
        examples.push({ tid, variant, bad,
          py: Object.fromEntries(bad.map((f) => [f, f === "stray_cells" ? strayA : rec[f]])),
          js: Object.fromEntries(bad.map((f) => [f, f === "stray_cells" ? strayB : got[f]])) });
      }
    }
  }
}

console.log(`replayed ${checked} recorded replies across ${Object.keys(data.tasks).length} tasks`);
console.log(`mismatches: ${mismatched}`);
for (const e of examples) {
  console.log(`  ${e.tid} / ${e.variant}: ${e.bad.join(", ")}`);
  console.log(`     python: ${JSON.stringify(e.py)}`);
  console.log(`     js    : ${JSON.stringify(e.js)}`);
}
if (mismatched) {
  console.log("\nFAIL, the JS scorer does not reproduce the Python verdicts.");
  process.exit(1);
}
console.log("\nPASS, the JS scorer reproduces every recorded Python verdict.");

// --- adversarial cross-check -------------------------------------------------
// The 384 replays above only cover replies these four models actually produced.
// A visitor can type things they never did: fenced blocks, duplicated objects,
// float and null answers, lowercase cell refs, no-op edits, truncated JSON.
// These cases were scored by the real Python scorer and the verdicts recorded;
// the port must match those too.

const cases = JSON.parse(readFileSync(new URL("./crosscheck_cases.json", import.meta.url)));
const pyRef = JSON.parse(readFileSync(new URL("./crosscheck_python.json", import.meta.url)));

let xChecked = 0, xBad = 0;
for (const tid of pyRef.task_ids) {
  const task = data.tasks[tid];
  cases.forEach((raw, i) => {
    const got = judge(task, parseResponse(raw));
    const py = pyRef.verdicts[tid][i];
    xChecked++;
    const bad = [...FIELDS, "stray_cells"].filter((f) => {
      const a = py[f] === undefined ? null : py[f];
      const b = got[f] === undefined ? null : got[f];
      return f === "stray_cells"
        ? JSON.stringify(a ?? null) !== JSON.stringify(b ?? null)
        : a !== b;
    });
    if (bad.length) {
      xBad++;
      if (xBad <= 8) {
        console.log(`  XCHECK ${tid} case#${i} ${bad.join(", ")}`);
        console.log(`     raw   : ${JSON.stringify(raw).slice(0, 90)}`);
        console.log(`     python: ${JSON.stringify(Object.fromEntries(bad.map(f => [f, py[f] ?? null])))}`);
        console.log(`     js    : ${JSON.stringify(Object.fromEntries(bad.map(f => [f, got[f] ?? null])))}`);
      }
    }
  });
}
console.log(`\nadversarial cross-check: ${xChecked} cases, ${xBad} mismatches`);
if (xBad) {
  console.log("FAIL, the port diverges on hand-written replies.");
  process.exit(1);
}
console.log("PASS, the port matches Python on adversarial input too.");
