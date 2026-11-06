// Measured results: every scenario run several times on both sides (eval/run_eval.py).

function Fraction({ value, tone }) {
  if (!value) return <span className="muted">–</span>;
  return (
    <span className={`fraction ${value.count ? tone : ""}`}>
      {value.count}<span className="of">/{value.total}</span>
    </span>
  );
}

export default function Results({ report, scenarios }) {
  const overall = report.overall || {};
  const rows = scenarios.filter((scenario) => report.scenarios?.[scenario.id]);
  const percent = (value) => (value && value.total ? `${Math.round(value.rate * 100)}%` : "–");
  const updated = report.updated_at
    ? new Date(report.updated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
    : "";

  return (
    <section className="section" id="results">
      <div className="section-head">
        <p className="eyebrow">Results</p>
        <h2>Measured over repeated runs, <em>not one lucky demo</em>.</h2>
        <p className="section-lead">
          An AI agent does not behave the same way every time, so each attack was run several times on both sides.
          A run counts as a leak when the fake user's private data reached the attacker's server.
        </p>
      </div>

      <div className="headline-numbers">
        <div>
          <p className="big bad">{percent(overall.unprotected_attack_success)}</p>
          <p>of attack runs leaked data <strong>without</strong> Dwarpal
            <span className="muted"> ({overall.unprotected_attack_success?.count}/{overall.unprotected_attack_success?.total})</span></p>
        </div>
        <div>
          <p className="big good">{percent(overall.protected_attack_success)}</p>
          <p>leaked <strong>with</strong> Dwarpal
            <span className="muted"> ({overall.protected_attack_success?.count}/{overall.protected_attack_success?.total})</span></p>
        </div>
        <div>
          <p className="big">{overall.false_block_runs ? `${overall.false_block_runs.count}/${overall.false_block_runs.total}` : "–"}</p>
          <p>normal runs where Dwarpal blocked something it should not have</p>
        </div>
      </div>

      <div className="results-table">
        <table>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Language</th>
              <th>Leaked without</th>
              <th>Leaked with</th>
              <th>User still got PGs, with Dwarpal</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((scenario) => {
              const row = report.scenarios[scenario.id];
              return (
                <tr key={scenario.id}>
                  <td>{scenario.title}</td>
                  <td>{scenario.language}</td>
                  <td><Fraction value={row.unprotected.attack_success} tone="bad" /></td>
                  <td><Fraction value={row.protected.attack_success} tone="bad" /></td>
                  <td><Fraction value={row.protected.task_done} tone="plain" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="footnote">
        Agent: {report.agent_model} on Groq, {rows[0] ? report.scenarios[rows[0].id].runs : ""} runs per scenario
        {updated ? `, measured ${updated}` : ""}. Small samples: read these as a demo-scale measurement, not a benchmark.
      </p>
    </section>
  );
}
