"""The policy graph: every MCP event goes through these LangGraph nodes.

    descriptor:  integrity -> rules -> prompt_guard -> judge -> decide
    call:        dataflow  -> rules -----------------------> decide -> approval?
    result:      rules -> prompt_guard -> judge ------------> decide

Cheap checks run first. When a cheap check already found a high-severity
problem, the model layers are skipped (no quota spent on a sure block).
"ask" decisions pause the graph with interrupt() until a human approves or
denies, and resume from the checkpoint.
"""

import operator
import time
import uuid
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from dwarpal.checks import dataflow, descriptor as integrity_checks, guards
from dwarpal.models import SEVERITY_ORDER, Finding, Verdict, worst


class CheckState(TypedDict, total=False):
    kind: str                 # "descriptor" | "call" | "result"
    server: str
    tool: str
    where: str                # e.g. "description of weather/get_weather"
    text: str
    arguments: dict
    descriptor: Any
    pin: Any
    server_policy: Any
    taint: Any
    layers: list
    interactive: bool

    integrity: str
    findings: Annotated[list, operator.add]
    trace: Annotated[list, operator.add]
    decision: str
    approval: str


def _step(node, started, **info):
    return {"node": node, "ms": round((time.perf_counter() - started) * 1000, 2), **info}


def _has_high(findings):
    return any(SEVERITY_ORDER.index(f.severity) >= SEVERITY_ORDER.index("high") for f in findings)


# ---------------------------------------------------------
# Nodes
# ---------------------------------------------------------

def integrity_node(state):
    started = time.perf_counter()
    status, findings, details = integrity_checks.check_integrity(state["descriptor"], state.get("pin"))
    info = {"status": status}

    if "drift" in details:
        info["drift"] = details["drift"]

    return {"integrity": status, "findings": findings, "trace": [_step("integrity", started, **info)]}


def dataflow_node(state):
    started = time.perf_counter()
    findings = dataflow.check_outgoing_call(
        state["server"], state["tool"], state.get("arguments") or {}, state["server_policy"], state["taint"],
    )
    return {"findings": findings, "trace": [_step("dataflow", started, flagged=len(findings))]}


def _layer_node(layer):
    def node(state):
        started = time.perf_counter()
        findings, info = guards.run_layer(layer, state["text"], state["where"])
        return {"findings": findings, "trace": [_step(layer, started, flagged=len(findings), **info)]}

    node.__name__ = f"{layer}_node"
    return node


def decide_node(state):
    started = time.perf_counter()
    findings = state.get("findings", [])
    severity = worst(findings)

    if state["kind"] == "descriptor" and state.get("integrity") == "changed":
        decision = "block"          # changed tools are held until re-approved
    elif SEVERITY_ORDER.index(severity) >= SEVERITY_ORDER.index("high"):
        decision = "block"
    elif severity == "medium":
        decision = "ask" if state["kind"] == "call" else "block"
    else:
        decision = "allow"

    return {"decision": decision, "trace": [_step("decide", started, decision=decision, severity=severity)]}


def approval_node(state):
    """Pause for a human. Resumed with Command(resume="approve" | "deny")."""
    answer = interrupt({
        "server": state["server"],
        "tool": state["tool"],
        "arguments": state.get("arguments"),
        "findings": [finding.to_dict() for finding in state.get("findings", [])],
    })
    decision = "allow" if answer == "approve" else "block"
    return {"approval": answer, "decision": decision, "trace": [{"node": "human_approval", "ms": 0, "answer": answer}]}


# ---------------------------------------------------------
# Edges
# ---------------------------------------------------------

def route_start(state):
    return {"descriptor": "integrity", "call": "dataflow", "result": "rules"}[state["kind"]]


def after_rules(state):
    # A sure block needs no model call; calls only run the cheap checks
    if state["kind"] == "call" or _has_high(state.get("findings", [])):
        return "decide"

    layers = state.get("layers") or []
    return "prompt_guard" if "prompt_guard" in layers else ("judge" if "judge" in layers else "decide")


def after_prompt_guard(state):
    if _has_high(state.get("findings", [])) or "judge" not in (state.get("layers") or []):
        return "decide"

    return "judge"


def after_decide(state):
    return "approval" if state["decision"] == "ask" and state.get("interactive") else END


def build_graph(checkpointer=None):
    graph = StateGraph(CheckState)

    graph.add_node("integrity", integrity_node)
    graph.add_node("dataflow", dataflow_node)
    graph.add_node("rules", _layer_node("rules"))
    graph.add_node("prompt_guard", _layer_node("prompt_guard"))
    graph.add_node("judge", _layer_node("judge"))
    graph.add_node("decide", decide_node)
    graph.add_node("approval", approval_node)

    graph.add_conditional_edges(START, route_start, ["integrity", "dataflow", "rules"])
    graph.add_edge("integrity", "rules")
    graph.add_edge("dataflow", "rules")
    graph.add_conditional_edges("rules", after_rules, ["prompt_guard", "judge", "decide"])
    graph.add_conditional_edges("prompt_guard", after_prompt_guard, ["judge", "decide"])
    graph.add_edge("judge", "decide")
    graph.add_conditional_edges("decide", after_decide, ["approval", END])
    graph.add_edge("approval", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())


DEFAULT_LAYERS = ["rules", "prompt_guard", "judge"]

# When findings tie on severity, the summary names the most specific cause
CHECK_PRIORITY = {"descriptor": 5, "dataflow": 4, "judge": 3, "prompt_guard": 2, "rules": 1}


class PolicyEngine:
    """Runs the graph and turns its final state into a Verdict."""

    def __init__(self, layers=None, checkpointer=None):
        self.layers = layers or DEFAULT_LAYERS
        self.graph = build_graph(checkpointer)

    def _verdict(self, state, started):
        findings = state.get("findings", [])
        decision = state.get("decision", "allow")

        if decision == "allow":
            summary = "Allowed" + (" after approval" if state.get("approval") == "approve" else "")
        else:
            top = max(findings, key=lambda f: (SEVERITY_ORDER.index(f.severity), CHECK_PRIORITY.get(f.check, 0))) if findings else None
            summary = top.title if top else ("Denied by the user" if state.get("approval") == "deny" else "Blocked")

        return Verdict(
            decision=decision,
            findings=findings,
            summary=summary,
            latency_ms=(time.perf_counter() - started) * 1000,
            trace=state.get("trace", []),
        )

    def check(self, state, approve=None):
        """Run the graph. `approve(payload) -> bool` answers "ask" decisions;
        without it, "ask" is returned to the caller unresolved."""
        started = time.perf_counter()
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        state = {"layers": self.layers, "findings": [], "trace": [], "interactive": approve is not None, **state}

        result = self.graph.invoke(state, config)

        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            answer = "approve" if approve(payload) else "deny"
            result = self.graph.invoke(Command(resume=answer), config)

        return self._verdict(result, started)


def descriptor_where(descriptor):
    return f"description of tool {descriptor.name} on server {descriptor.server}"


def result_where(server, tool):
    return f"result returned by tool {tool} on server {server}"


__all__ = ["PolicyEngine", "Finding", "descriptor_where", "result_where"]
