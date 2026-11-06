// The opening screen: the problem in one sentence, and a picture of where Dwarpal sits.

function GateDiagram() {
  // Agent on the left, three tool servers on the right, Dwarpal's gate between.
  const servers = [
    { y: 46, name: "pg_finder", note: "PG listings", tone: "ok" },
    { y: 130, name: "notes", note: "your phone, notes", tone: "private" },
    { y: 214, name: "weather", note: "third party", tone: "evil" },
  ];

  return (
    <svg className="gate-diagram" viewBox="0 0 520 260" role="img"
      aria-label="An AI agent reaches three tool servers through the Dwarpal gate. A harmful message from the weather server is stopped at the gate.">
      <defs>
        <path id="p-ok" d="M118 130 C 200 130, 200 46, 262 46 L 382 46" />
        <path id="p-notes" d="M118 130 L 382 130" />
        <path id="p-evil" d="M382 214 L 262 214 C 236 214, 236 214, 236 214" />
      </defs>

      {/* wires */}
      <g className="wire">
        <path d="M118 130 C 200 130, 200 46, 262 46 L 382 46" />
        <path d="M118 130 L 382 130" />
        <path d="M118 130 C 200 130, 200 214, 262 214 L 382 214" />
      </g>

      {/* agent */}
      <g className="node">
        <rect x="18" y="98" width="100" height="64" rx="10" />
        <text x="68" y="126" className="node-title">AI agent</text>
        <text x="68" y="144" className="node-note">talks to tools</text>
      </g>

      {/* the gate: two pillars and an arch */}
      <g className="gate">
        <path d="M222 236 V 60 a 26 26 0 0 1 52 0 V 236" />
        <text x="248" y="252" className="gate-label">Dwarpal</text>
      </g>

      {/* servers */}
      {servers.map((server) => (
        <g className={`node server ${server.tone}`} key={server.name}>
          <rect x="382" y={server.y - 26} width="122" height="52" rx="10" />
          <text x="443" y={server.y - 3} className="node-title">{server.name}</text>
          <text x="443" y={server.y + 14} className="node-note">{server.note}</text>
        </g>
      ))}

      {/* safe traffic passes the gate */}
      <circle r="4" className="packet">
        <animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#p-ok" /></animateMotion>
      </circle>
      <circle r="4" className="packet">
        <animateMotion dur="3.2s" begin="-1.6s" repeatCount="indefinite"><mpath href="#p-notes" /></animateMotion>
      </circle>

      {/* the attack is stopped at the gate */}
      <circle r="5" className="packet evil">
        <animateMotion dur="2.4s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.6;1" calcMode="linear">
          <mpath href="#p-evil" />
        </animateMotion>
        <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.62;0.75;1" dur="2.4s" repeatCount="indefinite" />
      </circle>
      <g className="stop">
        <circle cx="236" cy="214" r="11" />
        <path d="M231 209 l10 10 M241 209 l-10 10" />
        <animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.55;0.62;0.9;1" dur="2.4s" repeatCount="indefinite" />
      </g>
    </svg>
  );
}

export default function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero-copy">
        <p className="eyebrow">Security gateway for AI agents · द्वारपाल means gatekeeper</p>
        <h1>
          AI agents trust every tool they are given.
          <em> Dwarpal checks them first.</em>
        </h1>
        <p className="lead">
          Agents use tools through <abbr title="Model Context Protocol: the standard way AI agents connect to tools like search, email or files">MCP</abbr>.
          One bad tool can quietly tell the agent to send your data away, in English, Hindi, Hinglish or Kannada.
          Dwarpal sits between the agent and its tools, checks everything that passes, and stops it.
        </p>
        <div className="hero-actions">
          <a className="button primary" href="#playground">Try an attack</a>
          <a className="button ghost" href="#how">How it decides</a>
        </div>
        <ul className="hero-facts">
          <li><strong>4</strong> layers of checks</li>
          <li><strong>4</strong> languages tested</li>
          <li><strong>₹0</strong> to run, all free tiers</li>
        </ul>
      </div>
      <div className="hero-visual">
        <GateDiagram />
        <p className="caption">Normal requests pass through. The weather server's hidden order is stopped at the gate.</p>
      </div>
    </section>
  );
}
