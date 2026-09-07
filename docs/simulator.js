/**
 * Deterministic, single-car dry-track sandbox. Coefficients are illustrative.
 * It does not model traffic, overtaking, tyre allocation or sporting legality.
 * This is the same module used by the browser and the Node test suite.
 */
export const COMPOUNDS = Object.freeze({
  Soft: { offset: 0, wear: 1.35, code: "S" },
  Medium: { offset: 0.45, wear: 0.85, code: "M" },
  Hard: { offset: 0.9, wear: 0.55, code: "H" },
});

function finite(value, name, low, high) {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < low ||
    value > high
  ) {
    throw new RangeError(
      name + " must be between " + low + " and " + high + ".",
    );
  }
}

export function validateScenario(s) {
  finite(s.laps, "Race laps", 5, 100);
  if (!Number.isInteger(s.laps))
    throw new RangeError("Race laps must be an integer.");
  finite(s.baseLap, "Reference pace", 40, 240);
  finite(s.pitLoss, "Pit loss", 0, 60);
  finite(s.degradation, "Degradation", 0, 0.5);
  finite(s.fuelGain, "Fuel effect", 0, 0.1);
  finite(s.safetyLap, "Safety-car lap", 0, s.laps);
  if (!Number.isInteger(s.safetyLap))
    throw new RangeError("Safety-car lap must be an integer.");
}

export function validateStrategy(strategy, laps) {
  if (
    !strategy ||
    !Array.isArray(strategy.compounds) ||
    !Array.isArray(strategy.stops)
  ) {
    throw new TypeError("A strategy needs compounds and pit laps.");
  }
  if (
    strategy.compounds.length !== strategy.stops.length + 1 ||
    strategy.stops.length > 3
  ) {
    throw new RangeError(
      "Each stop must start one new stint (at most three stops).",
    );
  }
  if (strategy.compounds.some((c) => !Object.hasOwn(COMPOUNDS, c))) {
    throw new RangeError("Choose Soft, Medium or Hard.");
  }
  let previous = 0;
  for (const lap of strategy.stops) {
    if (!Number.isInteger(lap) || lap <= previous || lap >= laps) {
      throw new RangeError(
        "Pit laps must increase and fall before the final lap.",
      );
    }
    previous = lap;
  }
}

export function simulate(scenario, strategy, wearScale = 1) {
  validateScenario(scenario);
  validateStrategy(strategy, scenario.laps);
  finite(wearScale, "Wear multiplier", 0, 3);
  const laps = [];
  let stint = 0,
    age = 0,
    cumulative = 0;
  for (let lap = 1; lap <= scenario.laps; lap++) {
    const compound = strategy.compounds[stint];
    const tyre = COMPOUNDS[compound];
    const safety =
      scenario.safetyLap > 0 &&
      lap >= scenario.safetyLap &&
      lap < scenario.safetyLap + 3;
    // The SC window adds the same slowdown to both cars; it halves pit loss.
    const pace =
      scenario.baseLap +
      tyre.offset +
      tyre.wear * scenario.degradation * age * wearScale -
      scenario.fuelGain * (lap - 1) +
      (safety ? 15 : 0);
    const pit = strategy.stops.includes(lap);
    const pitLoss = pit ? scenario.pitLoss * (safety ? 0.5 : 1) : 0;
    const seconds = pace + pitLoss;
    cumulative += seconds;
    laps.push({ lap, compound, age, pit, safety, seconds, cumulative });
    if (pit) {
      stint++;
      age = 0;
    } else {
      age++;
    }
  }
  return { laps, total: cumulative, stops: strategy.stops.length };
}

export function compare(scenario, a, b) {
  const first = simulate(scenario, a),
    second = simulate(scenario, b);
  const delta = first.laps.map(
    (lap, i) => second.laps[i].cumulative - lap.cumulative,
  );
  const sensitivity = [0.7, 1, 1.3].map(
    (wear) =>
      simulate(scenario, b, wear).total - simulate(scenario, a, wear).total,
  );
  return {
    a: first,
    b: second,
    delta,
    finalDelta: second.total - first.total,
    sensitivity: [Math.min(...sensitivity), Math.max(...sensitivity)],
  };
}

export function formatTime(seconds) {
  finite(seconds, "Time", 0, 1000000);
  const ms = Math.round(seconds * 1000);
  const minutes = Math.floor(ms / 60000);
  const remainder = ms % 60000;
  return (
    minutes +
    ":" +
    Math.floor(remainder / 1000)
      .toString()
      .padStart(2, "0") +
    "." +
    (remainder % 1000).toString().padStart(3, "0")
  );
}

export function exportCSV(result) {
  const rows = [
    "lap,a_compound,a_seconds,a_cumulative,b_compound,b_seconds,b_cumulative,b_minus_a",
  ];
  result.a.laps.forEach((a, i) => {
    const b = result.b.laps[i];
    rows.push(
      [
        a.lap,
        a.compound,
        a.seconds.toFixed(3),
        a.cumulative.toFixed(3),
        b.compound,
        b.seconds.toFixed(3),
        b.cumulative.toFixed(3),
        result.delta[i].toFixed(3),
      ].join(","),
    );
  });
  return rows.join("\n") + "\n";
}
