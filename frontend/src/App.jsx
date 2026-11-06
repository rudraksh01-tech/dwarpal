import { useEffect, useMemo, useRef, useState } from "react";
import { API_URL, health, loadJSON, runLive } from "./api.js";
import { applyEvent, emptyRun, keyDecision } from "./run.js";
import Hero from "./components/Hero.jsx";
import Pipeline from "./components/Pipeline.jsx";
import TestMessage from "./components/TestMessage.jsx";
import Results from "./components/Results.jsx";
import { AgentPanel, AttackBrief, ScenarioPicker } from "./components/Playground.jsx";

const REPLAY_SECONDS = 14; // a recorded run is replayed in about this long

const STACK = [
  ["Gateway", "Python 3.12, FastAPI, MCP Python SDK 2"],
  ["Policy graph", "LangGraph, with human-approval interrupts"],
  ["Models", "Groq: gpt-oss-20b agent, Prompt Guard 2, gpt-oss-safeguard-20b judge"],
  ["Storage", "Postgres + pgvector (tool pins, audit log, known attacks)"],
  ["Cache", "Redis: verdict cache and rate limits"],
  ["Deploy", "Docker, Kubernetes, Helm (tested on kind in CI)"],
];

function Header({ live }) {
  return (
    <header className="site-header">
      <a href="#top" className="wordmark">Dwarpal</a>
      <nav aria-label="Sections">
        <a href="#playground">Playground</a>
        <a href="#how">How it decides</a>
        <a href="#results">Results</a>
        <a href="#test">Test a message</a>
        <a href="#inside">Inside</a>
      </nav>
      <span className={`server-state ${live}`} title="Status of the live demo server">
        {live === "online" ? "Live server ready" : live === "waking" ? "Waking live server…" : "Recorded mode"}
      </span>
    </header>
  );
}

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [examples, setExamples] = useState([]);
  const [selected, setSelected] = useState("rug_pull_hinglish");
  const [run, setRun] = useState(emptyRun());
  const [mode, setMode] = useState(null); // "replay" | "live" while running
  const [recordedAt, setRecordedAt] = useState(null);
  const [sample, setSample] = useState(null);
  const [evalReport, setEvalReport] = useState(null);
  const [live, setLive] = useState(API_URL ? "waking" : "offline");
  const [notice, setNotice] = useState("");
  const timers = useRef([]);
  const controller = useRef(null);

  useEffect(() => {
    loadJSON("/recordings/scenarios.json").then(setScenarios).catch(() => setNotice("Could not load the scenarios."));
    loadJSON("/recordings/checks.json").then(setExamples).catch(() => setExamples([]));
    loadJSON("/recordings/eval.json").then(setEvalReport).catch(() => setEvalReport(null));

    // Wake the free-tier backend now, so it is warm by the time someone presses "Run live"
    if (API_URL) {
      const abort = new AbortController();
      const timeout = setTimeout(() => abort.abort(), 90000);
      health(abort.signal)
        .then((info) => setLive(info.live_models ? "online" : "offline"))
        .catch(() => setLive("offline"))
        .finally(() => clearTimeout(timeout));
    }

    return () => timers.current.forEach(clearTimeout);
  }, []);

  const scenario = scenarios.find((item) => item.id === selected);
  const running = mode !== null;
  const decision = useMemo(() => keyDecision(run.protected.items), [run.protected.items]);

  const stop = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    controller.current?.abort();
    setMode(null);
  };

  const replay = async () => {
    stop();
    setNotice("");
    setRun(emptyRun());

    let recording;
    try {
      recording = await loadJSON(`/recordings/${selected}.json`);
    } catch {
      setNotice("No recording for this scenario yet.");
      return;
    }

    setRecordedAt(recording.recorded_at);
    setSample(recording.sample || null);
    setMode("replay");

    // Both sides start together; each keeps its own real timing, compressed
    const longest = Math.max(...recording.events.map((event) => event.t), 1);
    const scale = Math.min(1, (REPLAY_SECONDS * 1000) / longest);
    const ordered = recording.events.map((event, index) => ({ ...event, order: index }));

    for (const event of ordered) {
      const delay = Math.max(event.t * scale, event.order * 15) + 300;
      timers.current.push(setTimeout(() => setRun((state) => applyEvent(state, event)), delay));
    }

    const end = Math.max(...ordered.map((event) => Math.max(event.t * scale, event.order * 15))) + 600;
    timers.current.push(setTimeout(() => setMode(null), end));
  };

  const goLive = async () => {
    stop();
    setNotice("");
    setRecordedAt(null);
    setSample(null);
    setRun({ unprotected: { ...emptyRun().unprotected, running: true }, protected: { ...emptyRun().protected, running: true } });
    setMode("live");
    controller.current = new AbortController();

    try {
      await runLive({ scenario: selected, signal: controller.current.signal, onEvent: (event) => setRun((state) => applyEvent(state, event)) });
    } catch (error) {
      if (error.name !== "AbortError") {
        setNotice(`${error.message} You can still replay the recorded run.`);
        setRun(emptyRun());
      }
    } finally {
      setMode(null);
    }
  };

  const choose = (id) => {
    stop();
    setSelected(id);
    setRun(emptyRun());
    setRecordedAt(null);
    setSample(null);
  };

  return (
    <>
      <Header live={live} />
      <main>
        <Hero />

        <section className="section" id="playground">
          <div className="section-head">
            <p className="eyebrow">Playground</p>
            <h2>Same agent. Same question. <em>One of them is protected.</em></h2>
            <p className="section-lead">
              A PG-hunting assistant for Bengaluru uses three tools. The weather tool belongs to an attacker. Pick an
              attack, then watch both agents handle it at the same time. All people and numbers here are made up.
            </p>
          </div>

          <ScenarioPicker scenarios={scenarios} selected={selected} onSelect={choose} disabled={false} />
          <AttackBrief scenario={scenario} />

          <div className="run-bar">
            <button className="button primary" onClick={replay} disabled={running || !scenario}>
              {mode === "replay" ? "Replaying…" : "Replay a real run"}
            </button>
            <button className="button ghost" onClick={goLive} disabled={running || live !== "online"}
              title={live === "online" ? "Runs both agents on the real models now" : "The live server is not available right now"}>
              {mode === "live" ? "Running live…" : "Run it live"}
            </button>
            {running && <button className="link" onClick={stop}>Stop</button>}
            <p className="run-note">
              {recordedAt
                ? `Recorded ${new Date(recordedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })} from real model calls, replayed faster.`
                : live === "online" ? "Live runs call the real models (about 20–60 s on free tiers)." : "Replays are real recorded runs, so they work instantly."}
            </p>
          </div>
          {sample && scenario?.attack_type !== "none" && (
            <p className="sample-note">
              Showing run {sample.run} of {sample.runs}. Over all {sample.runs} runs, this attack leaked data{" "}
              <strong className="bad">{sample.unprotected_leaks} of {sample.runs}</strong> times without Dwarpal and{" "}
              <strong className="good">{sample.protected_leaks} of {sample.runs}</strong> times with it.
            </p>
          )}
          {notice && <p className="notice">{notice}</p>}

          <div className="panels">
            <AgentPanel side="unprotected" state={run.unprotected} userRequest={scenario?.user_request} />
            <AgentPanel side="protected" state={run.protected} userRequest={scenario?.user_request} />
          </div>
        </section>

        <Pipeline decision={decision} />

        {evalReport && <Results report={evalReport} scenarios={scenarios} />}

        <TestMessage examples={examples} live={live === "online"} />

        <section className="section" id="inside">
          <div className="section-head">
            <p className="eyebrow">Inside</p>
            <h2>What it is built with.</h2>
          </div>
          <dl className="stack">
            {STACK.map(([term, value]) => (
              <div key={term}><dt>{term}</dt><dd>{value}</dd></div>
            ))}
          </dl>
        </section>
      </main>

      <footer className="site-footer">
        <p>Built by <strong>Rudra Pratap Singh</strong>, Bengaluru.</p>
        <p className="muted">
          Defensive research. Every attack here targets only this demo's own local servers and fake data.
        </p>
      </footer>
    </>
  );
}
