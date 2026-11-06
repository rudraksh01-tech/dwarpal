import { useState } from "react";
import { checkText } from "../api.js";

const LAYERS = [
  { id: "rules", name: "Rules", note: "keyword patterns" },
  { id: "prompt_guard", name: "Prompt Guard 2", note: "Meta's classifier" },
  { id: "judge", name: "Policy judge", note: "reads intent" },
];

function LayerCard({ layer, result }) {
  if (!result) return <div className="layer idle"><h3>{layer.name}</h3><p className="muted">{layer.note}</p></div>;

  const unavailable = result.error || result.skipped;
  const flagged = result.flagged;
  const finding = result.findings?.[0];

  return (
    <div className={`layer ${unavailable ? "idle" : flagged ? "flag" : "pass"}`}>
      <h3>{layer.name}</h3>
      <p className="layer-verdict">{unavailable ? "unavailable" : flagged ? "Flagged" : "Looks safe"}</p>
      <p className="muted">
        {unavailable ? "model not reachable right now" : finding ? finding.detail : "Found nothing wrong."}
      </p>
      {result.score !== undefined && !unavailable && <p className="layer-meta">score {result.score}</p>}
      {result.ms !== undefined && <p className="layer-meta">{result.cached ? "cached" : `${Math.round(result.ms)} ms`}</p>}
    </div>
  );
}

export default function TestMessage({ examples, live }) {
  const [text, setText] = useState(examples[0]?.text || "");
  const [result, setResult] = useState(examples[0]?.result || null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const pick = (example) => {
    setText(example.text);
    setResult(example.result);
    setError("");
  };

  const run = async () => {
    const recorded = examples.find((example) => example.text === text.trim());
    if (recorded) return setResult(recorded.result);

    setStatus("loading");
    setError("");
    try {
      setResult(await checkText(text));
    } catch (problem) {
      setError(problem.message || "The live server is not reachable.");
    } finally {
      setStatus("idle");
    }
  };

  return (
    <section className="section" id="test">
      <div className="section-head">
        <p className="eyebrow">Test a message</p>
        <h2>Why one guard is <em>not enough</em>.</h2>
        <p className="section-lead">
          Paste anything a tool might say to an agent and see what each layer thinks. Try the polite example: the classic
          classifier calls it safe, the policy judge does not.
        </p>
      </div>

      <div className="tester">
        <div className="tester-input">
          <div className="examples">
            {examples.map((example) => (
              <button key={example.label} className={`chip ${text === example.text ? "on" : ""}`} onClick={() => pick(example)}>
                {example.label}
              </button>
            ))}
          </div>
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={5} maxLength={3000}
            aria-label="Text a tool might send to an agent" />
          <div className="tester-actions">
            <button className="button primary" onClick={run} disabled={!text.trim() || status === "loading"}>
              {status === "loading" ? "Checking…" : "Check with every layer"}
            </button>
            {!live && <span className="muted small">Examples are recorded; your own text needs the live server.</span>}
          </div>
          {error && <p className="error-text">{error}</p>}
        </div>

        <div className="layers">
          {LAYERS.map((layer) => <LayerCard key={layer.id} layer={layer} result={result?.layers?.[layer.id]} />)}
        </div>
      </div>
    </section>
  );
}
