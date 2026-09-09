const $ = (id) => document.getElementById(id);
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
const count = (value) => Number(value).toLocaleString("en-GB");
const number = (value) => Number(value).toFixed(3);
const label = (value) => escape(value.replaceAll("_", " "));
function table(caption, headers, rows) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${escape(caption)}">
    <table><caption>${escape(caption)}</caption><thead><tr>${headers.map((h) => `<th scope="col">${escape(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
export function renderCandidates(metrics) {
  const names = {
    tyre_strategy: "Opening tyre sequence",
    positioning: "Finishing position",
    lap_time: "Pit-filtered pace",
  };
  $("candidate-results").innerHTML = Object.entries(metrics.tasks)
    .map(([task, report]) => {
      const score =
        task === "tyre_strategy"
          ? (r) => (r.accuracy * 100).toFixed(1) + "%"
          : (r) => r.mae.toFixed(3);
      return table(
        names[task] + (task === "tyre_strategy" ? " · accuracy" : " · MAE"),
        ["Candidate", "2015 validation", "2016 test", "Selection"],
        Object.entries(report.validation).map(([name, validation]) => [
          label(name),
          score(validation),
          score(report.candidates_test[name]),
          name === report.selected ? "Selected on 2015" : "Comparison only",
        ]),
      );
    })
    .join("");
}
export function renderStints(research, event) {
  const rows = research.stints.events[event.id] ?? [];
  $("stint-study-context").textContent =
    `${event.name} · ${rows.reduce((n, r) => n + r.stints, 0)} qualifying stints with recorded dry conditions, exact pit-boundary agreement and at least six usable laps.`;
  $("stint-study-table").innerHTML = rows.length
    ? table(
        "Recorded stint-pace slopes · " + event.name,
        ["Compound", "Stints", "Median (s/lap)", "Middle 50% (s/lap)"],
        rows.map((r) => [
          escape(r.compound),
          count(r.stints),
          number(r.median),
          `${number(r.q25)} to ${number(r.q75)}`,
        ]),
      )
    : "<p class=empty-study>No stints meet this study's checks for this event. Choose another event; no wear estimate has been invented.</p>";
}
export function renderResearch(research) {
  const { quality, catalogue, stints } = research,
    joins = quality.joins;
  $("join-evidence").innerHTML = `
    <p>${count(joins.eligible_driver_races)} driver–race records have at least five usable laps.</p>
    <div class="join-strip" role="img" aria-label="${joins.previous_exact_name_matches} exact-name matches, ${joins.recovered_by_aliases} recovered by explicit aliases, ${joins.unmatched_records.length} unresolved">
      <span style="flex:${joins.previous_exact_name_matches}"></span><span class="recovered" style="flex:${joins.recovered_by_aliases}"></span><span class="unresolved"></span>
    </div>
    <dl class="join-counts"><div><dt>Exact names</dt><dd>${count(joins.previous_exact_name_matches)}</dd></div>
      <div><dt>Recovered aliases</dt><dd>+${joins.recovered_by_aliases}</dd></div>
      <div><dt>Unresolved</dt><dd>${joins.unmatched_records.length}</dd></div></dl>
    <p>Explicit mappings join variants such as “Filipe Nasr” and “Felipe Nasr”. Source names stay intact; unknown names are never fuzzy-matched.</p>
    <p class="helper">The remaining Button / Bahrain 2015 lap record conflicts with the official DNS classification. It stays excluded. Matching an identity does not verify every timing observation.</p>`;
  $("catalogue-summary").textContent =
    `${catalogue.summary.csv_files} CSV files contain ${catalogue.summary.distinct_csv_contents} distinct byte contents. ${catalogue.summary.workbooks} workbooks are catalogued by metadata only.`;
  const richer = catalogue.files.find((f) => f.path === "F1_data.csv");
  $("richer-summary").textContent = richer
    ? `F1_data.csv has ${count(richer.rows)} rows, sector times, track temperature and compounds—but no season column and ${count(richer.exact_duplicate_rows)} exact duplicate rows. It is not used for training.`
    : "The richer dataset has not been catalogued. It is not used for training.";
  const evaluation = stints.evaluation;
  $("drift-evaluation").innerHTML =
    `<p>${count(stints.audit.analysed_stints)} stints from ${count(stints.audit.aligned_driver_races)} driver–race records passed the alignment checks.</p>` +
    (evaluation.status === "evaluated"
      ? table(
          "Stint-slope prediction · MAE in s/lap of tyre age",
          ["Method", "2015 validation", "2016 test"],
          Object.keys(evaluation.validation).map((name) => [
            label(name),
            number(evaluation.validation[name]),
            number(evaluation.test[name]),
          ]),
        )
      : "<p>Not enough seasons for comparison.</p>");
  $("legacy-experiments").innerHTML = table(
    "Inspected historical experiments · not benchmark results",
    ["Experiment", "Why excluded"],
    catalogue.legacy_experiments.map((e) => [
      escape(e.path),
      e.reasons.map(escape).join("; "),
    ]),
  );
  $("source-catalogue").innerHTML = table(
    "Source inventory · full hashes in the JSON download",
    ["Original file", "Rows", "Role"],
    catalogue.files.map((f) => [
      escape(f.path),
      f.rows === undefined ? "Metadata only" : count(f.rows),
      label(f.role),
    ]),
  );
  $("stint-exclusions").innerHTML = table(
    "Driver–race exclusions · first failing check",
    ["Reason", "Records"],
    Object.entries(stints.audit.excluded_driver_races).map(([reason, n]) => [
      label(reason),
      count(n),
    ]),
  );
}
