import { useState } from "react";
import Markdown from "./Markdown.jsx";
import { KIND_LABEL, leakedIn, timeline } from "../run.js";

const LANGUAGE_SCRIPT = { Kannada: "kn", Hindi: "hi" };

export function ScenarioPicker({ scenarios, selected, onSelect, disabled }) {
  return (
    <div className="scenario-grid" role="radiogroup" aria-label="Choose an attack">
      {scenarios.map((scenario, index) => (
        <button
          key={scenario.id}
          role="radio"
          aria-checked={selected === scenario.id}
          className={`scenario ${selected === scenario.id ? "selected" : ""} ${scenario.attack_type === "none" ? "control" : ""}`}
          onClick={() => onSelect(scenario.id)}
          disabled={disabled}
        >
          <span className="scenario-index">{String(index + 1).padStart(2, "0")}</span>
          <span className="scenario-title">{scenario.title}</span>
          <span className="scenario-meta">
            <span className="tag quiet">{scenario.attack_type === "none" ? "control run" : scenario.attack_type.replaceAll("_", " ")}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

export function AttackBrief({ scenario, showOriginal, onToggle, disabled }) {
  if (!scenario) return null;
  const isControl = scenario.attack_type === "none";
  const original = scenario.original;
  const shown = showOriginal && original ? original : scenario;

  return (
    <div className="brief">
      <div className="brief-text">
        <h3>{isControl ? "No attack in this run" : "What the attacker did"}</h3>
        <p>{scenario.explain}</p>
        {original && (
          <div className="language-switch" role="group" aria-label="Language of the attack">
            <p className="switch-label">Attack language</p>
            <button className={!showOriginal ? "on" : ""} onClick={() => onToggle(false)} disabled={disabled}>English</button>
            <button className={showOriginal ? "on" : ""} onClick={() => onToggle(true)} disabled={disabled}>{original.language}</button>
            <p className="switch-note">
              {showOriginal
                ? `The same attack written in ${original.language}. English-trained guards often miss these; Dwarpal checks every language.`
                : `Switch to see the same attack in ${original.language}.`}
            </p>
          </div>
        )}
      </div>

      {!isControl && (
        <figure className="evidence">
          <figcaption>
            Hidden in the weather server's <strong>{shown.rug_pull ? "new tool description" : shown.where}</strong>
          </figcaption>
          <blockquote lang={LANGUAGE_SCRIPT[shown.language]}>{shown.attack_text}</blockquote>
          {showOriginal && shown.meaning && (
            <p className="meaning"><span>In English:</span> {shown.meaning}</p>
          )}
        </figure>
      )}
    </div>
  );
}

function ToolChecks({ checks }) {
  const [open, setOpen] = useState(false);
  const hidden = checks.filter((check) => check.decision !== "allow");

  return (
    <li className={`row checks ${hidden.length ? "alert" : ""}`}>
      <span className="row-icon shield" aria-hidden="true" />
      <div className="row-body">
        <p>
          Dwarpal checked <strong>{checks.length} tools</strong> before the agent saw them
          {hidden.length ? <>: <strong className="blocked-word">quarantined {hidden.length}</strong></> : ": all clean"}.
        </p>
        {hidden.map((check) => (
          <p className="row-detail" key={check.tool}>
            <code>{check.tool}</code> {check.summary}
          </p>
        ))}
        <button className="link" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} every tool</button>
        {open && (
          <ul className="check-list">
            {checks.map((check) => (
              <li key={`${check.server}/${check.tool}`} className={check.decision}>
                <code>{check.server}/{check.tool}</code>
                <span>{check.decision === "allow" ? (check.integrity === "unchanged" ? "unchanged" : "pinned") : "quarantined"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

function Shield({ event }) {
  const where = { call: "before the call left", result: "before the agent read the result" }[event.kind] || "";

  return (
    <li className="row shield-row">
      <span className="row-icon shield" aria-hidden="true" />
      <div className="row-body">
        <p>
          <strong className="blocked-word">Blocked {where}</strong> <code>{event.tool}</code>
        </p>
        <p className="row-detail">{event.summary}</p>
        {event.findings?.[0]?.detail && <p className="row-detail muted">{event.findings[0].detail}</p>}
      </div>
    </li>
  );
}

function Step({ step, side }) {
  const [open, setOpen] = useState(false);

  if (step.type === "phase") {
    return <li className="row phase"><p>{step.text}</p></li>;
  }

  if (step.type === "tool_call") {
    const leaks = side === "unprotected" ? leakedIn(step) : [];
    const args = JSON.stringify(step.arguments || {});

    return (
      <li className={`row call ${leaks.length ? "leak" : ""}`}>
        <span className="row-icon out" aria-hidden="true" />
        <div className="row-body">
          <p className="mono">
            <span className="fn">{step.tool}</span>(<span className="args">{args === "{}" ? "" : args}</span>)
          </p>
          {leaks.length > 0 && <p className="leak-note">Private data sent to the attacker's server</p>}
        </div>
      </li>
    );
  }

  if (step.type === "dwarpal_note") {
    return (
      <li className="row shield-row">
        <span className="row-icon shield" aria-hidden="true" />
        <div className="row-body">
          <p><strong className="blocked-word">Refused</strong> <code>{step.tool}</code></p>
          <p className="row-detail">{step.text.replace(/^\[Dwarpal\]\s*/, "")}</p>
        </div>
      </li>
    );
  }

  if (step.type === "tool_result") {

    return (
      <li className="row result">
        <span className="row-icon in" aria-hidden="true" />
        <div className="row-body">
          <button className="result-toggle mono" onClick={() => setOpen(!open)} aria-expanded={open}>
            {step.tool} returned {open ? "" : <span className="preview">{step.text.replace(/\s+/g, " ").slice(0, 70)}…</span>}
          </button>
          {open && <pre className="result-text">{step.text}</pre>}
        </div>
      </li>
    );
  }

  if (step.type === "answer") {
    return (
      <li className="row answer">
        <div className="row-body">
          <p className="answer-label">Agent's reply</p>
          <Markdown text={step.text} />
        </div>
      </li>
    );
  }

  return null;
}

function Outcome({ side, state }) {
  if (state.error) return <div className="outcome error">This run failed: {state.error}</div>;
  if (!state.done) return <div className="outcome pending">{state.running ? "Running…" : "Waiting to run"}</div>;

  const leaked = state.done.leaked || [];
  const blocked = state.done.blocked?.length || 0;

  if (leaked.length) {
    return (
      <div className="outcome leaked">
        <p className="outcome-head">Data leaked to the attacker</p>
        <ul>{leaked.map((item, i) => <li key={i}><span>{KIND_LABEL[item.kind] || item.kind}</span> {item.value}</li>)}</ul>
      </div>
    );
  }

  return (
    <div className={`outcome safe ${side}`}>
      <p className="outcome-head">Nothing leaked</p>
      <p>{side === "protected" ? (blocked ? `${blocked} attack step${blocked > 1 ? "s" : ""} stopped by Dwarpal` : "Nothing needed blocking") : "The agent did not follow the attack this time"}</p>
    </div>
  );
}

export function AgentPanel({ side, state, userRequest }) {
  const rows = timeline(state.items);
  const title = side === "protected" ? "With Dwarpal" : "Without Dwarpal";
  const subtitle = side === "protected" ? "Same agent, tools reached through the gateway" : "The agent talks to the tools directly";

  return (
    <article className={`panel ${side}`} aria-live="polite">
      <header className="panel-head">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        <span className={`panel-mark ${side}`} aria-hidden="true" />
      </header>

      <ol className="rows">
        <li className="row user">
          <p className="answer-label">User</p>
          <p>{userRequest}</p>
        </li>
        {rows.map((row, index) =>
          row.type === "tool_checks" ? <ToolChecks key={index} checks={row.checks} />
            : row.type === "shield" ? <Shield key={index} event={row.event} />
            : <Step key={index} step={row} side={side} />
        )}
        {state.running && <li className="row typing"><span /><span /><span /></li>}
      </ol>

      <Outcome side={side} state={state} />
    </article>
  );
}
