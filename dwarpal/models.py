"""Shared data types: tool descriptors, findings and verdicts."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Literal


Decision = Literal["allow", "block", "ask"]
Severity = Literal["info", "low", "medium", "high", "critical"]

SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


@dataclass(frozen=True)
class ToolDescriptor:
    """What an MCP server says about one tool."""

    server: str
    name: str
    description: str
    input_schema: dict

    @property
    def key(self):
        return f"{self.server}/{self.name}"

    def canonical(self):
        """Stable JSON of everything the model reads about the tool."""
        return json.dumps(
            {"name": self.name, "description": self.description, "input_schema": self.input_schema},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def fingerprint(self):
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def model_visible_text(self):
        """Description plus every string inside the schema.

        Attackers hide instructions in parameter descriptions, titles and
        defaults too ("full-schema poisoning"), so all of it is scanned.
        """
        parts = [self.description or ""]

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("description", "title", "default", "examples", "enum", "const") or isinstance(value, (dict, list)):
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, str):
                parts.append(node)

        walk(self.input_schema or {})
        return "\n".join(part for part in parts if part)


@dataclass
class Finding:
    """One reason to worry, from one check."""

    check: str          # "descriptor", "rules", "prompt_guard", "judge", "dataflow", "policy"
    severity: Severity
    title: str          # short, shown in the UI
    detail: str = ""    # one sentence explanation
    evidence: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def worst(findings):
    if not findings:
        return "info"

    return max((finding.severity for finding in findings), key=SEVERITY_ORDER.index)


@dataclass
class Verdict:
    decision: Decision
    findings: list
    summary: str = ""
    latency_ms: float = 0.0
    trace: list = field(default_factory=list)   # LangGraph nodes visited, for the UI timeline

    def to_dict(self):
        return {
            "decision": self.decision,
            "summary": self.summary,
            "severity": worst(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
            "latency_ms": round(self.latency_ms, 1),
            "trace": self.trace,
        }
