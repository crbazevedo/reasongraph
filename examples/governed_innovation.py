"""Worked example: a (generic) governed-agentic-innovation programme.

Builds a small reason-graph and runs one pass so you can watch deduction / induction / abduction /
decision act together. Then evolve it from the CLI, e.g.:

    python examples/governed_innovation.py
    reasongraph add-finding examples/governed_innovation.json T-INDEX proven --conf 0.8 --ev proof.md
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reasongraph import A, make_node, make_edge, new_graph, save, ReasonGraph  # noqa: E402

g = new_graph(thesis="principled governed agentic innovation (outer/inner loops)")
N, E = g["nodes"], g["edges"]
def node(*a, **k): N.append(make_node(*a, **k))
def edge(*a, **k): E.append(make_edge(*a, **k))

# --- established building blocks ---
node("C-SUBSTRATE", "contribution", "Governed execution substrate (waves + gates + isolation)",
     "proven", attrs=A(payoff=.5), statement="Concurrent agent units in isolated workspaces under verification gates.")
node("C-VTIERS", "contribution", "Tiered-authority governance (autonomy ladder)",
     "proven", attrs=A(payoff=.5), statement="A discrete authority ladder from autonomous to human-only.")

# --- accumulated findings (positive AND negative — both first-class) ---
node("F-BOUNDED-RETRY", "finding", "Bounded retry + escalation beats unbounded looping",
     "proven", attrs=A(info=.6), evidence=["external-benchmark: convergence study"])
node("F-NAIVE-OUTER", "finding", "A fully-autonomous outer loop overspends the shared budget",
     "refuted", attrs=A(info=.8),
     statement="A naive always-on autonomous agenda exhausts the budget before directed work arrives.")

# --- open frontier ---
node("T-INDEX", "target", "Attention index allocating one operator across inner + outer loops",
     "open", attrs=A(payoff=.9, ready=.8, fit=.95, info=.8, risk=.35))
node("T-PREEMPT", "target", "Economic preemption: when an outer loop may interrupt an inner loop",
     "open", attrs=A(payoff=.7, info=.6))
node("T-AUTONOMOUS-OUTER", "target", "Safely-autonomous outer agenda (advisory-until-admitted)",
     "open", attrs=A(payoff=.75, info=.7, risk=.4))
node("T-BUDGET-SPLIT", "target", "Separate outer-loop budget line (guardrail vs starving directed work)",
     "open", attrs=A(payoff=.6, ready=.7, info=.6))

edge("C-SUBSTRATE", "T-INDEX", "enables")
edge("C-VTIERS", "T-INDEX", "enables")
edge("T-INDEX", "T-PREEMPT", "enables")
edge("F-BOUNDED-RETRY", "T-PREEMPT", "supports")
edge("C-VTIERS", "T-AUTONOMOUS-OUTER", "enables")
edge("F-NAIVE-OUTER", "T-AUTONOMOUS-OUTER", "enables")   # a REFUTED prerequisite -> blocks the target
edge("T-BUDGET-SPLIT", "T-AUTONOMOUS-OUTER", "enables")  # the repair route abduction will point at

out = os.path.join(os.path.dirname(__file__), "governed_innovation.json")
save(g, out)
print(f"wrote {out}\n")
ReasonGraph(g).report()
