import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { simulate, compare, formatTime, exportCSV } from "../docs/simulator.js";

const scenario = {
  laps: 10,
  baseLap: 90,
  pitLoss: 20,
  degradation: 0,
  fuelGain: 0,
  safetyLap: 0,
};
const noStop = { compounds: ["Soft"], stops: [] };
const oneStop = { compounds: ["Soft", "Soft"], stops: [5] };

test("closed-form constant pace and exact pit-loss accounting", () => {
  assert.equal(simulate(scenario, noStop).total, 900);
  assert.equal(simulate(scenario, oneStop).total, 920);
});
test("identical strategies have zero cumulative gap and sensitivity", () => {
  const result = compare({ ...scenario, degradation: 0.12 }, oneStop, oneStop);
  assert.deepEqual(result.delta, Array(10).fill(0));
  assert.deepEqual(result.sensitivity, [0, 0]);
});
test("pit lap uses old tyres; following lap resets age", () => {
  const result = simulate({ ...scenario, degradation: 0.1 }, oneStop);
  assert.equal(result.laps[4].age, 4);
  assert.equal(result.laps[4].pit, true);
  assert.equal(result.laps[5].age, 0);
  assert.ok(Math.abs(result.laps[4].seconds - 110.54) < 1e-9);
  assert.equal(result.laps[5].seconds, 90);
});
test("SC shared slowdown cancels; only a stop within the window earns discount", () => {
  const s = { ...scenario, safetyLap: 4 };
  assert.equal(compare(s, noStop, oneStop).finalDelta, 10);
  assert.equal(compare({ ...s, safetyLap: 6 }, noStop, oneStop).finalDelta, 20);
  assert.equal(simulate({ ...s, safetyLap: 10 }, noStop).total, 915);
});
test("fuel effect is applied once per elapsed lap", () => {
  assert.equal(simulate({ ...scenario, fuelGain: 0.1 }, noStop).total, 895.5);
});
test("invalid scenarios reject nonfinite, fractional and out-of-range inputs", () => {
  for (const update of [
    { laps: 0 },
    { laps: 10.5 },
    { laps: 101 },
    { pitLoss: NaN },
    { baseLap: Infinity },
    { degradation: -1 },
    { fuelGain: 0.2 },
    { safetyLap: 11 },
    { safetyLap: 2.5 },
    { pitLoss: "20" },
  ]) {
    assert.throws(
      () => simulate({ ...scenario, ...update }, noStop),
      RangeError,
    );
  }
});
test("invalid strategies reject unordered, repeated, final-lap and missing stops", () => {
  for (const strategy of [
    { compounds: ["Soft"], stops: [5] },
    { compounds: ["Unknown"], stops: [] },
    { compounds: ["Soft", "Soft"], stops: [10] },
    { compounds: ["Soft", "Soft"], stops: [0] },
    { compounds: ["Soft", "Soft"], stops: [2.5] },
    { compounds: ["Soft", "Soft", "Soft"], stops: [5, 5] },
    { compounds: ["Soft", "Soft", "Soft"], stops: [7, 3] },
    { compounds: ["Soft", "Soft"], stops: [NaN] },
  ])
    assert.throws(() => simulate(scenario, strategy), RangeError);
  assert.throws(() => simulate(scenario, null), TypeError);
});
test("degradation sensitivity spans the base result; inputs stay immutable", () => {
  const s = Object.freeze({ ...scenario, degradation: 0.2, pitLoss: 0 });
  const result = compare(s, noStop, oneStop);
  assert.ok(
    result.sensitivity[0] <= result.finalDelta &&
      result.finalDelta <= result.sensitivity[1],
  );
  assert.ok(simulate(s, oneStop).total < simulate(s, noStop).total);
  assert.ok(Math.abs(result.finalDelta + 6.75) < 1e-9);
  assert.deepEqual(oneStop.stops, [5]);
});
test("CSV has one row per lap, fixed columns and finite values", () => {
  const rows = exportCSV(compare(scenario, noStop, oneStop))
    .trim()
    .split("\n");
  assert.equal(rows.length, 11);
  assert.equal(rows[0].split(",").length, 8);
  assert.equal(rows.at(-1).split(",").at(-1), "20.000");
  assert.ok(
    rows
      .slice(1)
      .every((row) => !row.includes("NaN") && row.split(",").length === 8),
  );
});
test("time formatting carries rounding across minutes", () => {
  assert.equal(formatTime(59.9996), "1:00.000");
  assert.equal(formatTime(90), "1:30.000");
  assert.throws(() => formatTime(-1), RangeError);
});
test("every exported race supports the default strategies", () => {
  const archive = JSON.parse(
    readFileSync(new URL("../docs/data/events.json", import.meta.url)),
  );
  assert.equal(archive.schemaVersion, 1);
  assert.equal(archive.events.length, 21);
  for (const event of archive.events) {
    const s = {
      ...scenario,
      laps: event.laps,
      baseLap: event.referencePace,
      degradation: 0.1,
    };
    const strategy = {
      compounds: ["Soft", "Medium"],
      stops: [Math.round(event.laps * 0.43)],
    };
    assert.ok(Number.isFinite(simulate(s, strategy).total));
    assert.equal(event.year, 2016);
    assert.ok(event.drivers.length > 0 && event.pace.length > 0);
  }
});
