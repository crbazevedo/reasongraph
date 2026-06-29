"""Dogfood: reasongraph's OWN roadmap, modeled as a reason-graph.

The shipped pieces are `contribution`/proven nodes; the backlog is `target` nodes (open). Dependency
edges encode what each item needs. Running a pass lets the engine rank what to build next — and
`add-finding` records each item as it ships, so the roadmap evolves instead of being rewritten.

Two layers of nodes:
  * the STARTER BACKLOG (the original CLI/tooling targets), and
  * the RESEARCH-DERIVED nodes — findings and targets distilled from the four reasoning/KR deep-dives
    in docs/RESEARCH-NOTES.md (the inference triad, knowledge representation, inference engines /
    belief revision, and decision/evidence theory). This is the abduction→graph loop in action.

    python examples/reasongraph_roadmap.py            # build the graph + run one pass
    reasongraph pass examples/reasongraph_roadmap.json
    reasongraph add-finding examples/reasongraph_roadmap.json T-STATUS-DERIVED proven --conf 0.9
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reasongraph import A, make_node, make_edge, new_graph, save, ReasonGraph  # noqa: E402

g = new_graph(thesis="trustworthy auditable substrate for the agentic outer loop — "
                     "pillar 1: sound deductive core (trust is load-bearing); "
                     "pillar 2: defensible decision layer; pillar 3: lean & adoptable")
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
node("C-DOCS", "contribution", "README + METHODOLOGY + SCHEMA + RESEARCH-NOTES docs",
     "proven", attrs=A(payoff=.4))
node("C-TESTS", "contribution", "Deterministic tests for deduction/decision/evolution",
     "proven", attrs=A(payoff=.5))

# --- starter backlog: three shipped, the rest open ---
node("T-VALIDATE", "target", "`reasongraph validate` — schema/edge lint (dangling/unknown/cycles)",
     "proven", attrs=A(payoff=.7, effort=.3, tract=.9, ready=.9, fit=.85, info=.4, risk=.1),
     evidence=["reasongraph/engine.py: validate()"])
node("T-EXPORT", "target", "`reasongraph export --mermaid|--dot` — status-colored visualization",
     "proven", attrs=A(payoff=.8, effort=.35, tract=.85, ready=.9, fit=.75, info=.4, risk=.15),
     evidence=["reasongraph/engine.py: to_mermaid()/to_dot()"])
node("T-JSON", "target", "`pass --json` + `reasongraph show <node>` for tooling",
     "proven", attrs=A(payoff=.7, effort=.3, tract=.9, ready=.9, fit=.7, info=.5, risk=.1),
     evidence=["reasongraph/engine.py: pass_data()/node_view()"])
node("T-SEED", "target", "`reasongraph seed <name>` — scaffold a seed.py + empty graph",
     "open", attrs=A(payoff=.55, effort=.3, tract=.85, ready=.9, fit=.6, info=.3, risk=.1))
node("T-ABDUCE", "target", "`reasongraph abduce --run` — pipe tasks to an LLM, write nodes back",
     "proven", attrs=A(payoff=.8, effort=.55, tract=.55, ready=.6, fit=.7, info=.6, risk=.35),
     # fit recalibrated .85 -> .7: valuable adoption tooling (pillar 3), but not load-bearing for trust
     evidence=["reasongraph/engine.py: abduce_payload()/ingest_abduced() + CLI --run (LLM external)"])
node("T-SNAPSHOT", "target", "snapshot/history: a passes/ log + `diff` between two passes",
     "open", attrs=A(payoff=.6, effort=.5, tract=.65, ready=.6, fit=.65, info=.55, risk=.2))
node("T-CONF", "target", "opt-in confidence auto-aggregation from evidence[]",
     "open", attrs=A(payoff=.55, effort=.45, tract=.6, ready=.7, fit=.6, info=.5, risk=.25))
node("T-HTML", "target", "no-deps static HTML viewer of the graph + ranked frontier",
     "open", attrs=A(payoff=.75, effort=.6, tract=.6, ready=.5, fit=.7, info=.4, risk=.25))
node("T-EXAMPLE2", "target", "a second worked example in a different domain (security audit)",
     "proven", attrs=A(payoff=.65, effort=.45, tract=.8, ready=.9, fit=.75, info=.45, risk=.15),
     evidence=["examples/security_audit.py — ported via GraphConfig only, no engine changes"])

# --- research-derived FINDINGS (see docs/RESEARCH-NOTES.md) ---
node("F-BLOCK-ONEHOP", "finding",
     "Block propagation WAS one-hop, not transitive (grandchild of a refuted node = AWAITING)",
     "proven", attrs=A(info=.8),
     statement="Verified by reproduction: the original deduction() inspected only immediate "
               "prerequisites, so a refutation blocked children but not grandchildren. RESOLVED by "
               "T-BLOCK-TRANSITIVE — deduction now propagates BLOCKED across the reachable subgraph.",
     evidence=["reproduction 2026-06: P refuted, C blocked, GC awaiting", "docs/RESEARCH-NOTES.md §3",
               "fixed by T-BLOCK-TRANSITIVE"])
node("F-FIT-WEAK-LEVER", "finding",
     "strategic_fit (weight .12) is too weak to express thesis priority against unlock-centrality (.20)",
     "proven", attrs=A(info=.7),
     statement="Dogfood 2026-06: after honestly raising fit on the pillar-1 correctness cluster, the "
               "engine still ranked the high-centrality T-ABDUCE top. Re-pointing the programme via "
               "strategic_fit alone cannot override a hub's unlock-centrality — motivates revisiting "
               "the decision weights (T-DECISION-ECONOMY).",
     evidence=["dogfood pass: fit-bumped cluster, T-ABDUCE still #1 by centrality"])
node("T-ADOPTER-KIT", "target",
     "Adopter upgrade kit: CHANGELOG + SemVer + version/migrate + UPGRADING guide",
     "proven", attrs=A(payoff=.7, effort=.4, tract=.8, ready=.9, fit=.85, info=.4, risk=.15),
     statement="Operator-requested: external adopters need change logs, an install-update path, a "
               "way to learn + apply new features to a live project, and graph backward-compatibility.",
     evidence=["CHANGELOG.md", "docs/UPGRADING.md", "reasongraph/cli.py: version/migrate + --config"])
node("F-GRAPH-BACKWARD-COMPAT", "finding",
     "Existing reasongraph/v1 graphs load and run unchanged — all 0.2.0 changes are additive",
     "proven", attrs=A(info=.6),
     statement="Schema stays v1; the engine reads optional node fields defensively; migrate is "
               "idempotent + non-destructive. Verified by a legacy-graph load test + a migrate test.",
     evidence=["tests: legacy graph loads/runs; migrate backfills + idempotent"])
node("F-PORT-CONFIG-ONLY", "finding",
     "Ported to a second domain (security audit) with ONLY GraphConfig changes — no engine edits",
     "proven", attrs=A(info=.6),
     statement="examples/security_audit.py reuses the engine/modes/decision/loop verbatim; only the "
               "status ladder, kind vocabulary, and weights changed. The 'domain-invariant' claim is "
               "earned, not asserted.",
     evidence=["examples/security_audit.py runs a clean pass under a security GraphConfig"])
node("F-CLI-CONFIG-FIXED", "finding",
     "CLI commands hardcoded the default GraphConfig — a ported graph couldn't be passed/validated via CLI",
     "proven", attrs=A(info=.65),
     statement="Discovered building T-EXAMPLE2: `reasongraph validate/pass` on security_audit.json "
               "used the default ladder, so custom statuses (confirmed/false-positive) misclassified "
               "and emitted spurious warnings. RESOLVED by T-CLI-CONFIG (a shared --config option).")
node("T-CLI-CONFIG", "target",
     "Let the CLI load a domain GraphConfig (e.g. --config module:NAME) so ported graphs work end-to-end",
     "proven", attrs=A(payoff=.65, effort=.4, tract=.75, ready=.85, fit=.8, info=.45, risk=.2),
     evidence=["reasongraph/cli.py: shared --config MODULE:NAME / PATH.py:NAME on every command"])
node("F-TOP-ROBUST-TAIL-FRAGILE", "finding",
     "The top recommendation is weight-robust; only the mid-frontier ordering is fragile",
     "proven", attrs=A(info=.6),
     statement="sensitivity audit (2026-06): the #1 pick is STABLE under every single-weight ±20% "
               "perturbation, while ~9 mid-frontier nodes change rank. Refines F-FIT-WEAK-LEVER: "
               "'what to do next' is trustworthy; deeper ranks should not be over-interpreted.",
     evidence=["reasongraph sensitivity examples/reasongraph_roadmap.json"])
node("F-FIREWALL-GROUNDED", "finding",
     "The LLM-out-of-deduction/decision firewall is theory-aligned (Peirce generation/justification)",
     "proven", attrs=A(info=.5),
     statement="Abduction = hypothesis generation; ranking/testing are deduction+induction. Keeping "
               "the LLM out of the deterministic modes is exactly this split — a feature, not an "
               "accident (cf. the IBE conflation).",
     evidence=["docs/RESEARCH-NOTES.md §1"])

# --- research-derived TARGETS: belief-revision / argumentation cluster (highest leverage) ---
node("T-STATUS-DERIVED", "target",
     "Status as a pure function of current evidence, recomputed each pass (recovery-by-construction)",
     "proven", attrs=A(payoff=.8, effort=.5, tract=.7, ready=.8, fit=.85, info=.6, risk=.3),
     statement="Never mutate-and-forget; recomputing makes deduction correctly non-monotonic — a "
               "refutation removes READY, overturning it restores READY. Keystone for the cluster.",
     evidence=["reasongraph/engine.py: is_frontier() derived membership + recovery"])
node("T-BLOCK-TRANSITIVE", "target",
     "Block as a transitive closure over prerequisite edges (TMS-style invalidation)",
     "proven", attrs=A(payoff=.75, effort=.3, tract=.85, ready=.9, fit=.8, info=.6, risk=.25),
     statement="Fix F-BLOCK-ONEHOP: a descendant of a refuted node should be BLOCKED, not AWAITING.",
     evidence=["reasongraph/engine.py: transitive deduction() via memoized DFS"])
# pillar 1 (sound deductive core): strategic_fit raised — trust is load-bearing, this is the priority.
node("T-OR-JUSTIFICATIONS", "target",
     "Disjunctive prerequisite-sets — BLOCK only when ALL alternative justifications are dead",
     "open", attrs=A(payoff=.7, effort=.6, tract=.55, ready=.5, fit=.9, info=.55, risk=.4),
     statement="JTMS keeps a node IN if any justification is valid; pure-conjunction prereqs cannot "
               "model a claim provable two ways.")
node("T-GROUNDED-EXTENSION", "target",
     "Compute the grounded extension over the negative sub-graph (Dung reinstatement)",
     "open", attrs=A(payoff=.75, effort=.65, tract=.5, ready=.5, fit=.92, info=.65, risk=.45),
     statement="A refute-of-a-refuter should reinstate the original claim; the grounded extension is "
               "unique, polynomial, skeptical — ideal for an auditable engine.")
node("T-BLOCK-EXPLAIN", "target",
     "A BLOCK carries its minimal set of refuted ancestors (nogood / causal frontier)",
     "proven", attrs=A(payoff=.6, effort=.3, tract=.85, ready=.9, fit=.88, info=.4, risk=.15),
     evidence=["reasongraph/engine.py: blocking_causes() + node_view.blocked_by + report"])

# --- research-derived TARGETS: abduction / induction cluster ---
node("T-DECISION-ECONOMY", "reframe",
     "Name the decision weights after Peirce's economy-of-research axes (cost/value/caution/breadth)",
     "open", attrs=A(payoff=.5, effort=.2, tract=.9, ready=.9, fit=.75, info=.35, risk=.1))
node("T-ABDUCE-MINIMALITY", "target",
     "Rank abduction tasks partly by parsimony (smaller graph delta preferred)",
     "open", attrs=A(payoff=.55, effort=.4, tract=.6, ready=.6, fit=.65, info=.45, risk=.25))
node("T-ABDUCE-COVERAGE", "target",
     "Track hypothesis diversity/coverage to guard the 'bad lot' (best-of-a-poor-set)",
     "open", attrs=A(payoff=.6, effort=.55, tract=.45, ready=.5, fit=.6, info=.6, risk=.35))
node("T-EVIDENCE-TYPED", "target",
     "Tag evidence enumerative vs eliminative + PROV source/quality; generalize on eliminative breadth",
     "open", attrs=A(payoff=.6, effort=.4, tract=.7, ready=.8, fit=.65, info=.5, risk=.2))
node("T-SUPPORT-SEMANTICS", "reframe",
     "Specify the BAF reading of `supports` and split negatives into undercut vs rebut",
     "open", attrs=A(payoff=.55, effort=.45, tract=.6, ready=.6, fit=.6, info=.45, risk=.3))

# --- research-derived TARGETS: decision / evidence-under-uncertainty cluster ---
node("T-SUBJECTIVE-LOGIC", "target",
     "Confidence via a subjective-logic opinion (Beta from evidence counts; capped by uncertainty mass)",
     "open", attrs=A(payoff=.7, effort=.5, tract=.6, ready=.7, fit=.7, info=.55, risk=.3),
     statement="'Confidence capped by evidence quality' IS subjective logic: conf = (r+a·W)/(r+s+W). "
               "Cumulative fusion for independent evidence, averaging for correlated.")
node("T-NONCOMPENSATORY-GATE", "target",
     "Make readiness/risk an eligibility veto before scoring (ELECTRE-style, anti-compensation)",
     "open", attrs=A(payoff=.65, effort=.35, tract=.75, ready=.85, fit=.7, info=.5, risk=.25))
node("T-WEIGHT-SENSITIVITY", "target",
     "Weight-sensitivity report: perturb each weight ±20% and flag any frontier rank flip",
     "proven", attrs=A(payoff=.6, effort=.35, tract=.8, ready=.85, fit=.75, info=.55, risk=.15),
     evidence=["reasongraph/engine.py: weight_sensitivity() + `sensitivity` CLI"])
node("T-INFO-EVPI", "target",
     "Ground info_value as a deterministic EVPI swing (decision-change if the node resolves either way)",
     "open", attrs=A(payoff=.65, effort=.55, tract=.55, ready=.6, fit=.65, info=.6, risk=.35))
node("T-CENTRALITY-DAG", "target",
     "Extend unlock_centrality to full attenuated DAG reachability (Katz-on-a-DAG, one reverse pass)",
     "open", attrs=A(payoff=.6, effort=.4, tract=.7, ready=.8, fit=.65, info=.45, risk=.25))

# --- every backlog item rests on the shipped engine/CLI ---
TARGETS = ("T-SEED", "T-ABDUCE", "T-SNAPSHOT", "T-CONF", "T-HTML", "T-EXAMPLE2",
           "T-STATUS-DERIVED", "T-BLOCK-TRANSITIVE", "T-OR-JUSTIFICATIONS", "T-GROUNDED-EXTENSION",
           "T-BLOCK-EXPLAIN", "T-DECISION-ECONOMY", "T-ABDUCE-MINIMALITY", "T-ABDUCE-COVERAGE",
           "T-EVIDENCE-TYPED", "T-SUPPORT-SEMANTICS", "T-SUBJECTIVE-LOGIC", "T-NONCOMPENSATORY-GATE",
           "T-WEIGHT-SENSITIVITY", "T-INFO-EVPI", "T-CENTRALITY-DAG", "T-CLI-CONFIG")
for t in TARGETS:
    edge("C-ENGINE", t, "enables")
edge("C-CLI", "T-CLI-CONFIG", "enables")
edge("F-CLI-CONFIG-FIXED", "T-CLI-CONFIG", "supports")   # the gap motivates the fix
edge("C-CLI", "T-ADOPTER-KIT", "enables")
edge("F-GRAPH-BACKWARD-COMPAT", "T-ADOPTER-KIT", "supports")

# --- starter-backlog inter-dependencies ---
edge("T-VALIDATE", "T-ABDUCE", "enables")    # write LLM-returned nodes back only if we can lint them
edge("T-VALIDATE", "T-SEED", "enables")      # a scaffold should emit a graph that validates
edge("T-JSON", "T-HTML", "enables")          # the viewer consumes structured pass output
edge("T-JSON", "T-SNAPSHOT", "enables")      # diffing passes is cleaner over structured output
edge("T-EXPORT", "T-HTML", "enables")        # the viewer reuses the export's status-coloring
edge("C-TESTS", "T-VALIDATE", "supports")

# --- research cluster dependencies (the unlock structure the decision layer rewards) ---
edge("T-STATUS-DERIVED", "T-BLOCK-TRANSITIVE", "enables")    # recompute-each-pass underpins the fix
edge("T-STATUS-DERIVED", "T-OR-JUSTIFICATIONS", "enables")
edge("T-STATUS-DERIVED", "T-GROUNDED-EXTENSION", "enables")
edge("T-OR-JUSTIFICATIONS", "T-GROUNDED-EXTENSION", "enables")
edge("F-BLOCK-ONEHOP", "T-BLOCK-TRANSITIVE", "supports")     # the verified finding motivates the fix
edge("F-FIREWALL-GROUNDED", "T-DECISION-ECONOMY", "supports")
edge("F-FIT-WEAK-LEVER", "T-DECISION-ECONOMY", "supports")
edge("F-TOP-ROBUST-TAIL-FRAGILE", "T-DECISION-ECONOMY", "supports")
edge("T-ABDUCE", "T-ABDUCE-MINIMALITY", "enables")
edge("T-ABDUCE", "T-ABDUCE-COVERAGE", "enables")
edge("T-SUBJECTIVE-LOGIC", "T-CONF", "enables")
edge("T-EVIDENCE-TYPED", "T-CONF", "enables")
edge("T-WEIGHT-SENSITIVITY", "T-DECISION-ECONOMY", "supports")

out = os.path.join(os.path.dirname(__file__), "reasongraph_roadmap.json")
save(g, out)
print(f"wrote {out}\n")
ReasonGraph(g).report()
