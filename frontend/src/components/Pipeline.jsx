// How Dwarpal decides: the policy graph, explained, with the last run's real trace on top.

const NODES = [
  {
    id: "integrity",
    name: "Tool integrity",
    tech: "SHA-256 pin + embedding drift",
    what: "Remembers exactly what each tool said when it was approved. If a tool quietly rewrites itself later (a rug pull), it is hidden until a human re-approves it.",
  },
  {
    id: "dataflow",
    name: "Data flow",
    tech: "taint tracking across servers",
    what: "Remembers your private values (phone, notes) returned by trusted tools, and stops them from travelling to an untrusted server, whatever language the attack used.",
  },
  {
    id: "rules",
    name: "Rules",
    tech: "multilingual patterns, ~0.1 ms",
    what: "Catches blatant attacks in English, Hindi, Hinglish, Kannada and Kanglish: 'ignore previous instructions', 'user ko mat batana', hidden tags, invisible characters.",
  },
  {
    id: "prompt_guard",
    name: "Prompt Guard 2",
    tech: "Meta's 86M classifier",
    what: "A well-known jailbreak classifier. Good at loud attacks, but polite ones ('for accuracy, include the phone number') slip past it.",
  },
  {
    id: "judge",
    name: "Policy judge",
    tech: "gpt-oss-safeguard-20b + written policy",
    what: "Reads intent: does a weather tool really need your phone number? Catches the polite attacks the classifier misses. Verdicts are cached, so each text is judged once.",
  },
  {
    id: "decide",
    name: "Decide",
    tech: "allow · block · ask a human",
    what: "Combines the findings. Sure attacks are blocked; borderline calls (your own phone number to a third party) pause and ask you first.",
  },
];

function stepFor(trace, id) {
  return trace?.find((step) => step.node === id);
}

function status(step) {
  if (!step) return "skipped";
  if (step.node === "decide") return step.decision;
  if (step.node === "integrity") return step.status === "changed" ? "flag" : "pass";
  if (step.error || step.skipped) return "skipped";
  return step.flagged ? "flag" : "pass";
}

export default function Pipeline({ decision }) {
  const trace = decision?.trace;

  return (
    <section className="section" id="how">
      <div className="section-head">
        <p className="eyebrow">How it decides</p>
        <h2>Every tool, call and result goes through <em>one policy graph</em>.</h2>
        <p className="section-lead">
          Built with LangGraph. Cheap checks run first; if they already found a sure attack, the slower model checks are
          skipped. {trace ? "Highlighted: what happened in the run above." : "Run an attack above to see a real trace here."}
        </p>
      </div>

      {decision && (
        <p className="trace-summary">
          <span className={`pill-${decision.decision}`}>{decision.decision}</span>
          <code>{decision.server}/{decision.tool}</code> · {decision.summary} · {Math.round(decision.latency_ms)} ms
        </p>
      )}

      <ol className="pipeline">
        {NODES.map((node, index) => {
          const step = stepFor(trace, node.id);
          const state = trace ? status(step) : "idle";

          return (
            <li key={node.id} className={`stage ${state}`}>
              <span className="stage-index">{index + 1}</span>
              <h3>{node.name}</h3>
              <p className="stage-tech">{node.tech}</p>
              <p className="stage-what">{node.what}</p>
              {trace && (
                <p className="stage-result">
                  {state === "skipped" ? "not needed" : state === "flag" ? "found a problem" : state === "pass" ? "clean" : state}
                  {step && step.ms !== undefined && state !== "skipped" ? ` · ${step.ms < 1 ? "<1" : Math.round(step.ms)} ms` : ""}
                  {step?.cached ? " · cached" : ""}
                  {step?.drift !== undefined ? ` · drift ${step.drift}` : ""}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
