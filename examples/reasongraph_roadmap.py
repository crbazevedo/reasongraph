"""Dogfood: reasongraph's OWN roadmap, modeled as a reason-graph.

The shipped pieces are `contribution` nodes (proven); the starter backlog is `target` nodes
(open). Dependency edges encode what each backlog item needs. Running a pass over this graph lets
the engine itself rank what to build next — and `add-finding` records each item as it ships, so the
roadmap evolves instead of being rewritten.

    python examples/reasongraph_roadmap.py            # build the graph + run one pass
    reasongraph pass examples/reasongraph_roadmap.json
    reasongraph add-finding examples/reasongraph_roadmap.json T-VALIDATE proven --conf 0.9 --ev cli.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reasongraph import A, make_node, make_edge, new_graph, save, ReasonGraph  # noqa: E402

g = new_graph(thesis="a lean, public, stdlib-only governed outer-loop engine people can adopt")
N, E = g["nodes"], g["edges"]
def node(*a, **k): N.append(make_node(*a, **k))
def edge(*a, **k): E.append(make_edge(*a, **k))

# --- shipped building blocks (the engine as it stands today) ---
node("C-ENGINE", "contribution", "Four-mode engine (deduction/induction/abduction/decision)",
     "proven", attrs=A(payoff=.6),
     statement="Peirce's triad + a deterministic decision layer over a typed claim graph.")
node("C-SCHEMA", "contribution", "Schema + tunable GraphConfig (status ladder / weights / kinds)",
     "proven", attrs=A(payoff=.5))
node("C-CLI", "contribution", "CLI: `pass` + `add-finding`",
     "proven", attrs=A(payoff=.5))
node("C-EXAMPLE", "contribution", "Worked example (governed_innovation) + generated JSON",
     "proven", attrs=A(payoff=.4))
node("C-DOCS", "contribution", "README + METHODOLOGY + SCHEMA docs",
     "proven", attrs=A(payoff=.4))
node("C-TESTS", "contribution", "Deterministic tests for deduction/decision/evolution",
     "proven", attrs=A(payoff=.5))

# --- the starter backlog, as open targets on the frontier ---
node("T-VALIDATE", "target", "`reasongraph validate` — schema/edge lint (dangling/unknown/cycles)",
     "open", attrs=A(payoff=.7, effort=.3, tract=.9, ready=.9, fit=.85, info=.4, risk=.1),
     statement="A pure linter: dangling edges, unknown status/kind/relation, prerequisite cycles.")
node("T-EXPORT", "target", "`reasongraph export --mermaid|--dot` — status-colored visualization",
     "open", attrs=A(payoff=.8, effort=.35, tract=.85, ready=.9, fit=.75, info=.4, risk=.15))
node("T-JSON", "target", "`pass --json` + `reasongraph show <node>` for tooling",
     "open", attrs=A(payoff=.7, effort=.3, tract=.9, ready=.9, fit=.7, info=.5, risk=.1))
node("T-SEED", "target", "`reasongraph seed <name>` — scaffold a seed.py + empty graph",
     "open", attrs=A(payoff=.55, effort=.3, tract=.85, ready=.9, fit=.6, info=.3, risk=.1))
node("T-ABDUCE", "target", "`reasongraph abduce --run` — pipe tasks to an LLM, write nodes back",
     "open", attrs=A(payoff=.8, effort=.55, tract=.55, ready=.6, fit=.85, info=.6, risk=.35))
node("T-SNAPSHOT", "target", "snapshot/history: a passes/ log + `diff` between two passes",
     "open", attrs=A(payoff=.6, effort=.5, tract=.65, ready=.6, fit=.65, info=.55, risk=.2))
node("T-CONF", "target", "opt-in confidence auto-aggregation from evidence[]",
     "open", attrs=A(payoff=.55, effort=.45, tract=.6, ready=.7, fit=.6, info=.5, risk=.25))
node("T-HTML", "target", "no-deps static HTML viewer of the graph + ranked frontier",
     "open", attrs=A(payoff=.75, effort=.6, tract=.6, ready=.5, fit=.7, info=.4, risk=.25))
node("T-EXAMPLE2", "target", "a second worked example in a different domain (security audit)",
     "open", attrs=A(payoff=.65, effort=.45, tract=.8, ready=.9, fit=.75, info=.45, risk=.15))

# --- every backlog item rests on the shipped engine/CLI ---
for t in ("T-VALIDATE", "T-EXPORT", "T-JSON", "T-SEED", "T-ABDUCE",
          "T-SNAPSHOT", "T-CONF", "T-HTML", "T-EXAMPLE2"):
    edge("C-ENGINE", t, "enables")
for t in ("T-VALIDATE", "T-EXPORT", "T-JSON", "T-SEED", "T-ABDUCE", "T-SNAPSHOT"):
    edge("C-CLI", t, "enables")

# --- inter-backlog dependencies (the unlock structure the decision layer rewards) ---
edge("T-VALIDATE", "T-ABDUCE", "enables")   # write LLM-returned nodes back only if we can lint them
edge("T-VALIDATE", "T-SEED", "enables")     # a scaffold should emit a graph that validates
edge("T-JSON", "T-HTML", "enables")         # the viewer consumes structured pass output
edge("T-JSON", "T-SNAPSHOT", "enables")     # diffing passes is cleaner over structured output
edge("T-EXPORT", "T-HTML", "enables")       # the viewer reuses the export's status-coloring
edge("C-TESTS", "T-VALIDATE", "supports")   # validation is the deterministic-hygiene sibling of tests

out = os.path.join(os.path.dirname(__file__), "reasongraph_roadmap.json")
save(g, out)
print(f"wrote {out}\n")
ReasonGraph(g).report()
