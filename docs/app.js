import { COMPOUNDS, compare, exportCSV, formatTime } from "./simulator.js";
import { renderResearch, renderStints, renderCandidates } from "./research.js";

const $ = (id) => document.getElementById(id);
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
const signed = (value) => (value > 0 ? "+" : "") + value.toFixed(1);
let archive, metrics, research, event, strategies, result;
const colour = (compound) => "compound-" + compound.replaceAll(" ", "-");

function setTab(name, focus = false) {
  for (const item of tabNames) {
    const selected = item === name,
      tab = $("tab-" + item);
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $("panel-" + item).hidden = !selected;
  }
  if (focus) $("tab-" + name).focus();
}
const tabNames = ["lab", "explorer", "models", "research"];
for (const name of tabNames) {
  $("tab-" + name).addEventListener("click", () => setTab(name));
  $("tab-" + name).addEventListener("keydown", (e) => {
    const idx = tabNames.indexOf(name);
    const next = {
      ArrowRight: (idx + 1) % tabNames.length,
      ArrowLeft: (idx + tabNames.length - 1) % tabNames.length,
      Home: 0,
      End: tabNames.length - 1,
    }[e.key];
    if (next !== undefined) {
      e.preventDefault();
      setTab(tabNames[next], true);
    }
  });
}

function defaults(stops) {
  return {
    compounds: stops === 1 ? ["Soft", "Medium"] : ["Soft", "Soft", "Medium"],
    stops:
      stops === 1
        ? [Math.round(event.laps * 0.43)]
        : [Math.round(event.laps * 0.29), Math.round(event.laps * 0.63)],
  };
}
function scenario() {
  return {
    laps: event.laps,
    baseLap: event.referencePace,
    pitLoss: Number($("pit-loss").value),
    degradation: Number($("degradation").value),
    fuelGain: 0.03,
    safetyLap: Number($("safety-lap").value),
  };
}
function setEvent(id) {
  event = archive.events.find((e) => e.id === id);
  $("event").value = id;
  $("explore-event").value = id;
  $("lap-count").textContent = event.laps;
  $("reference-pace").textContent = formatTime(event.referencePace);
  $("safety-lap").innerHTML =
    '<option value="0">No safety car</option>' +
    Array.from(
      { length: event.laps - 1 },
      (_, i) =>
        '<option value="' + (i + 1) + '">From lap ' + (i + 1) + "</option>",
    ).join("");
  strategies = [defaults(1), defaults(2)];
  renderEditors();
  update();
  renderExplorer();
}
function renderEditors() {
  $("strategy-editors").innerHTML = strategies
    .map((s, idx) => {
      const letter = idx === 0 ? "A" : "B";
      return (
        '<article class="strategy ' +
        (idx ? "b" : "a") +
        '">' +
        '<div class="strategy-top"><span class="strategy-id">' +
        letter +
        '</span><label class="strategy-title" for="stops-' +
        idx +
        '">Strategy ' +
        letter +
        '</label><select id="stops-' +
        idx +
        '" aria-label="Number of stops for strategy ' +
        letter +
        '">' +
        '<option value="1"' +
        (s.stops.length === 1 ? " selected" : "") +
        ">One stop</option>" +
        '<option value="2"' +
        (s.stops.length === 2 ? " selected" : "") +
        ">Two stops</option></select>" +
        '<span class="strategy-total" id="total-' +
        idx +
        '"></span></div>' +
        '<div class="stint-editor">' +
        s.compounds
          .map((c, i) => {
            const input =
              '<div class="stint-field"><label for="compound-' +
              idx +
              "-" +
              i +
              '">Stint ' +
              (i + 1) +
              '</label><select id="compound-' +
              idx +
              "-" +
              i +
              '" aria-label="Strategy ' +
              letter +
              " stint " +
              (i + 1) +
              ' compound">' +
              Object.keys(COMPOUNDS)
                .map(
                  (comp) =>
                    "<option" +
                    (c === comp ? " selected" : "") +
                    ">" +
                    comp +
                    "</option>",
                )
                .join("") +
              "</select></div>";
            if (i >= s.stops.length) return input;
            return (
              input +
              '<div class="stint-field pit-field"><label for="pit-' +
              idx +
              "-" +
              i +
              '">Pit after</label><input type="number" min="1" max="' +
              (event.laps - 1) +
              '" step="1" id="pit-' +
              idx +
              "-" +
              i +
              '" value="' +
              s.stops[i] +
              '" aria-label="Strategy ' +
              letter +
              " pit stop " +
              (i + 1) +
              ' after lap"></div>'
            );
          })
          .join("") +
        '</div><div class="stint-timeline" id="timeline-' +
        idx +
        '"></div></article>'
      );
    })
    .join("");
  strategies.forEach((s, idx) => {
    $("stops-" + idx).addEventListener("change", (e) => {
      strategies[idx] = defaults(Number(e.target.value));
      renderEditors();
      update();
      $("stops-" + idx).focus();
    });
    s.compounds.forEach((_, i) =>
      $("compound-" + idx + "-" + i).addEventListener("change", (e) => {
        strategies[idx].compounds[i] = e.target.value;
        update();
      }),
    );
    s.stops.forEach((_, i) =>
      $("pit-" + idx + "-" + i).addEventListener("input", (e) => {
        strategies[idx].stops[i] = Number(e.target.value);
        update();
      }),
    );
  });
}
function timeline(strategy, element) {
  const boundaries = [0, ...strategy.stops, event.laps];
  element.innerHTML = strategy.compounds
    .map(
      (c, i) =>
        '<span class="stint-block ' +
        colour(c) +
        '" style="width:' +
        ((boundaries[i + 1] - boundaries[i]) / event.laps) * 100 +
        '%" title="' +
        c +
        ": laps " +
        (boundaries[i] + 1) +
        "–" +
        boundaries[i + 1] +
        '">' +
        COMPOUNDS[c].code +
        " · " +
        (boundaries[i + 1] - boundaries[i]) +
        "</span>",
    )
    .join("");
  element.setAttribute(
    "aria-label",
    strategy.compounds
      .map(
        (c, i) => c + " for " + (boundaries[i + 1] - boundaries[i]) + " laps",
      )
      .join(", "),
  );
}
function drawChart(element, points, description, delta = true) {
  const mobile = window.innerWidth <= 760;
  const W = mobile ? 380 : 880,
    H = mobile ? 220 : 260,
    left = 45,
    right = 15,
    top = 16,
    bottom = 35;
  element.setAttribute("viewBox", "0 0 " + W + " " + H);
  const min = Math.min(...points.map((p) => p.y), delta ? 0 : Infinity);
  const max = Math.max(...points.map((p) => p.y), delta ? 0 : -Infinity);
  const pad = Math.max((max - min) * 0.15, 1),
    low = min - pad,
    high = max + pad;
  const x = (value) =>
    left + ((value - 1) / Math.max(event.laps - 1, 1)) * (W - left - right);
  const y = (value) =>
    top + ((high - value) / (high - low)) * (H - top - bottom);
  let markup =
    "<title>" +
    escape(description) +
    "</title><desc>" +
    escape(description) +
    ". Tabular or text summaries are available beside this chart.</desc>";
  for (let i = 0; i <= 4; i++) {
    const value = low + ((high - low) * i) / 4,
      yy = y(value);
    markup +=
      '<line class="grid" x1="' +
      left +
      '" x2="' +
      (W - right) +
      '" y1="' +
      yy +
      '" y2="' +
      yy +
      '"/>' +
      '<text x="' +
      (left - 9) +
      '" y="' +
      (yy + 3) +
      '" text-anchor="end">' +
      value.toFixed(0) +
      "</text>";
  }
  if (delta)
    markup +=
      '<line class="zero" x1="' +
      left +
      '" x2="' +
      (W - right) +
      '" y1="' +
      y(0) +
      '" y2="' +
      y(0) +
      '"/>';
  if (delta)
    strategies.forEach((s, i) =>
      s.stops.forEach((lap) => {
        markup +=
          '<line x1="' +
          x(lap) +
          '" x2="' +
          x(lap) +
          '" y1="' +
          top +
          '" y2="' +
          (H - bottom) +
          '" stroke="' +
          (i ? "#5cb6b9" : "#7295c6") +
          '" stroke-opacity=".4" stroke-dasharray="2 6"/>';
      }),
    );
  const path = points
    .map(
      (p, i) => (i ? "L" : "M") + x(p.x).toFixed(2) + "," + y(p.y).toFixed(2),
    )
    .join(" ");
  markup +=
    '<path d="' +
    path +
    '" fill="none" stroke="#6ad1cf" stroke-width="2.5" stroke-linejoin="round"/>';
  const ticks = mobile ? 3 : 5;
  for (let i = 0; i <= ticks; i++) {
    const lap = Math.round(1 + ((event.laps - 1) * i) / ticks);
    markup +=
      '<text x="' +
      x(lap) +
      '" y="' +
      (H - 12) +
      '" text-anchor="middle">' +
      lap +
      "</text>";
  }
  markup += '<text x="0" y="' + (H - 12) + '">LAP</text>';
  element.setAttribute("aria-label", description);
  element.removeAttribute("aria-labelledby");
  element.innerHTML = markup;
}
function update() {
  $("pit-loss-value").textContent = $("pit-loss").value + " s";
  $("degradation-value").textContent =
    Number($("degradation").value).toFixed(2) + " s/lap";
  try {
    result = compare(scenario(), strategies[0], strategies[1]);
    $("simulation-error").hidden = true;
    $("download").disabled = false;
    document.querySelector(".verdict").hidden = false;
    $("gap-chart").parentElement.hidden = false;
    strategies.forEach((s, i) => {
      timeline(s, $("timeline-" + i));
      $("total-" + i).textContent = formatTime(
        i ? result.b.total : result.a.total,
      );
    });
    drawChart(
      $("gap-chart"),
      result.delta.map((d, i) => ({ x: i + 1, y: d })),
      "Cumulative B minus A time; final difference " +
        signed(result.finalDelta) +
        " seconds",
    );
    const equal = Math.abs(result.finalDelta) < 0.05;
    $("winner").textContent = equal
      ? "The strategies finish level."
      : "Strategy " +
        (result.finalDelta > 0 ? "A" : "B") +
        " is " +
        Math.abs(result.finalDelta).toFixed(1) +
        " s quicker.";
    const stopDifference =
      strategies[1].stops.length - strategies[0].stops.length;
    $("outcome").textContent =
      stopDifference === 0
        ? "Same stop count. The difference comes from compounds and timing."
        : "Fresh-tyre pace trades off against " +
          Math.abs(stopDifference) +
          " additional stop.";
    $("sensitivity").textContent =
      signed(result.sensitivity[0]) +
      " to " +
      signed(result.sensitivity[1]) +
      " s";
  } catch (error) {
    result = null;
    $("simulation-error").hidden = false;
    $("simulation-error").textContent = error.message;
    $("download").disabled = true;
    document.querySelector(".verdict").hidden = true;
    $("gap-chart").parentElement.hidden = true;
    [0, 1].forEach((i) => {
      $("total-" + i).textContent = "Check pit laps";
      $("timeline-" + i).innerHTML = "";
    });
  }
}
function renderExplorer() {
  renderStints(research, event);
  const duplicateGrid = event.quality.duplicateGridSlots;
  $("archive-quality").textContent =
    "Source-data check: " +
    (duplicateGrid.length
      ? "repeated grid slot(s) " + duplicateGrid.join(", ") + ". "
      : "no repeated numeric grid slots. ") +
    "Records are shown as supplied; this is not a verified, complete classification.";
  $("archive-meta").textContent =
    event.year +
    " · " +
    event.name +
    " · Recorded conditions: " +
    event.condition +
    " · " +
    event.drivers.length +
    " driver records";
  $("archive-caption").textContent =
    event.name + " — recorded opening to final stint";
  $("stint-rows").innerHTML = event.drivers
    .map(
      (d) =>
        "<tr><td>" +
        escape(d.id) +
        "</td><td>" +
        (d.grid ?? "Pit/unknown") +
        " → " +
        (d.finish ?? "Unclassified") +
        '</td><td><div class="stint-timeline">' +
        d.stints
          .map(
            (s) =>
              '<span class="stint-block ' +
              escape(colour(s.compound)) +
              '" style="width:' +
              (s.laps ? Math.min((s.laps / event.laps) * 100, 100) : 8) +
              '%" title="' +
              escape(s.compound) +
              ": " +
              (s.laps ?? "unknown") +
              ' laps">' +
              escape(s.compound) +
              " · " +
              (s.laps ?? "?") +
              "</span>",
          )
          .join("") +
        "</div></td></tr>",
    )
    .join("");
  drawChart(
    $("pace-chart"),
    event.pace.map((p) => ({ x: p.lap, y: p.seconds })),
    "Historical median recorded pace by lap for " + event.name,
    false,
  );
}
function renderMetrics() {
  renderCandidates(metrics);
  const names = {
    tyre_strategy: "Opening tyre sequence",
    positioning: "Finishing position",
    lap_time: "Pit-filtered pace",
  };
  $("metric-cards").innerHTML = Object.entries(metrics.tasks)
    .map(([task, r]) => {
      const classification = task === "tyre_strategy";
      const value = classification
        ? (r.test.accuracy * 100).toFixed(1) + "%"
        : r.test.mae.toFixed(2);
      const baseline = classification
        ? (r.baseline_test.accuracy * 100).toFixed(1) + "%"
        : r.baseline_test.mae.toFixed(2);
      return (
        '<article class="metric-card"><h3>' +
        names[task] +
        '</h3><div class="big-metric">' +
        value +
        "</div><small>" +
        (classification
          ? "Accuracy · higher is better"
          : (task === "lap_time" ? "Seconds" : "Places") +
            " MAE · lower is better") +
        "</small><dl><div><dt>Selected on 2015</dt><dd>" +
        escape(r.selected.replaceAll("_", " ")) +
        "</dd></div><div><dt>Baseline on 2016</dt><dd>" +
        baseline +
        "</dd></div><div><dt>Test records / events</dt><dd>" +
        r.rows.test_2016 +
        " / " +
        r.events.test +
        "</dd></div>" +
        (classification
          ? "<div><dt>Unseen-label records</dt><dd>" +
            r.unseen_test_label_rows +
            "</dd></div>"
          : "") +
        "</dl></article>"
      );
    })
    .join("");
  $("per-race-report").innerHTML = Object.entries(metrics.tasks)
    .map(
      ([task, r]) =>
        "<h3>" +
        names[task] +
        "</h3><p>Race-mean " +
        (task === "tyre_strategy" ? "accuracy" : "MAE") +
        " interval: " +
        r.event_bootstrap_95_interval.map((v) => v.toFixed(3)).join("–") +
        '</p><div class="table-scroll" tabindex="0" role="region" aria-label="Per-event results"><table><thead><tr><th>Event</th><th>Records</th><th>' +
        (task === "tyre_strategy" ? "Accuracy" : "MAE") +
        "</th></tr></thead><tbody>" +
        r.per_event
          .map(
            (e) =>
              "<tr><td>" +
              escape(e.event_id) +
              "</td><td>" +
              e.rows +
              "</td><td>" +
              (task === "tyre_strategy"
                ? (e.accuracy * 100).toFixed(1) + "%"
                : e.mae.toFixed(3)) +
              "</td></tr>",
          )
          .join("") +
        "</tbody></table></div>",
    )
    .join("");
}

async function start() {
  const responses = await Promise.all(
    ["./data/events.json", "./data/metrics.json", "./data/research.json"].map(
      (path) => fetch(path + "?v=2.1.0"),
    ),
  );
  if (responses.some((r) => !r.ok))
    throw new Error(
      "The archive could not load. Refresh the page or try again later.",
    );
  [archive, metrics, research] = await Promise.all(
    responses.map((r) => r.json()),
  );
  if (
    !archive.events?.length ||
    metrics.schema_version !== 2 ||
    research.schema_version !== 1 ||
    !research.catalogue?.files?.length
  )
    throw new Error("The data bundle is incomplete. Rebuild the demo export.");
  const options = archive.events
    .map(
      (e) =>
        '<option value="' +
        escape(e.id) +
        '">' +
        escape(e.name) +
        " · " +
        e.year +
        "</option>",
    )
    .join("");
  $("event").innerHTML = options;
  $("explore-event").innerHTML = options;
  const initial =
    archive.events.find((e) => e.circuit === "bahrain") ?? archive.events[0];
  setEvent(initial.id);
  renderMetrics();
  renderResearch(research);
  $("view-evidence").addEventListener("click", () => setTab("research", true));
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      update();
      renderExplorer();
    }, 100);
  });
  $("load-status").hidden = true;
  $("workspace").hidden = false;
  ["event", "explore-event"].forEach((id) =>
    $(id).addEventListener("change", (e) => setEvent(e.target.value)),
  );
  ["pit-loss", "degradation", "safety-lap"].forEach((id) =>
    $(id).addEventListener("input", update),
  );
  $("reset").addEventListener("click", () => {
    $("pit-loss").value = 22;
    $("degradation").value = 0.1;
    setEvent(event.id);
  });
  $("download").addEventListener("click", () => {
    if (!result) return;
    const blob = new Blob([exportCSV(result)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download = "pit-window-" + event.circuit + "-scenario.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}
start().catch((error) => {
  $("load-status").hidden = true;
  $("load-error").hidden = false;
  $("load-error").textContent =
    error.message +
    " For local use, serve docs/ over HTTP rather than opening the file directly.";
});
