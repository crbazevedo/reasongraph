# Methodology

This is the deeper guide to the four inference modes and how to port them. The README is the
overview; this is enough to rebuild or adapt the capability. The reference implementation is
`reasongraph/engine.py` (~150 lines, stdlib).

## The bet

A programme is a set of interdependent **claims** that carry evidence. Treat the roadmap as a typed
graph of those claims and run **Peirce's inference triad + a decision layer** over it. The split
that makes it trustworthy: *deduction* and *decision* are deterministic code (reproducible,
auditable); *induction-as-generalization* and *abduction* are where an LLM proposes new structure —
but the LLM never scores and never decides.

## The four modes (algorithms)

Build an index once: for each node, its **prerequisites** (incoming `enables`/`depends-on`), what it
**feeds**, and its **negative** edges.

### Deduction — *what's reachable, what broke* (deterministic)
For each **open** node, look at its prerequisites:
```
ref_prereqs  = prereqs whose status is REFUTED
open_prereqs = prereqs whose status is neither PROVEN nor REFUTED
if ref_prereqs:            BLOCKED   # a proven failure invalidates dependents
elif open_prereqs == []:   READY     # everything it needs is proven
else:                      AWAITING  # near-ready if exactly one is missing
```
Logical entailment over the graph: it tells you what is *now reachable* and what a fresh refutation
just *broke*.

### Induction — *confidence + generalization* (rule, then LLM)
Aggregate `evidence[]` into `confidence`: independent/external support raises it, thin data caps it,
refuting evidence lowers it. **Generalization candidate:** a proven *finding* with ≥2 independent
supports → flag "propose a generalized node"; an LLM writes it. (This is how several narrow results
get noticed as one general claim.)

### Abduction — *what a surprise demands* (LLM pass)
Emit a hypothesis task for each **surprise**; an LLM turns each into a new `hypothesis`/`reframe`
node with an `abduced-from` edge. Three triggers:
1. **Refutation** → "explain *why* it failed and add the reframe / weaker-but-true claim / repair
   path that resolves it."
2. **Blocked high-payoff target** → "abduce a repair routing around the refuted prerequisite."
3. **High-information node** → "enumerate the 2–3 outcomes (positive *and* negative) and their
   downstream entailments, so the result is decision-useful either way."

### Decision — *what to do next* (deterministic, transparent)
```
score = .26·payoff + .20·unlock_centrality + .16·tractability·(1−.5·effort)
      + .12·readiness·ready_bonus + .12·strategic_fit + .12·info_value − .10·risk
ready_bonus       = 1.0 READY / 0.6 AWAITING / 0.2 else
unlock_centrality = min(1, ( Σ_1hop payoff + ½·Σ_2hop payoff ) / 3)
```
Two deliberate properties: **unlock-centrality** rewards moves that unblock many others (not just
high-payoff leaves); **info-value** lets a likely-*negative* result that resolves a fork still rank.

## The live loop

```
1. pass            → ranked frontier + deduction/induction/abduction outputs (+ a decision-log line)
2. pick + execute  → usually a derive/verify-plus-adversarial-critique step, or an experiment
3. add-finding     → record the result (positive OR negative); re-propagates and re-scores
4. abduction pass  → an LLM turns emitted tasks into new nodes; they enter the frontier next cycle
5. repeat
```

## Invariants that make it work

- **Negative results are findings, not failures** — they propagate, prune, and spawn.
- **Derived state recovers; it is never a one-way stamp** — readiness *and* frontier membership are
  recomputed from current status each pass (`is_frontier` = intent ∧ status-unresolved), so
  overturning a finding restores the node and its dependents. This is the bidirectional belief
  revision a Truth Maintenance System guarantees (Doyle 1979); `add-finding` records evidence, it
  does not mutate derived flags.
- **Confidence is capped by evidence quality** — `empirical-thin` can't reach high confidence until
  an enabling experiment lands.
- **Keep the seed canonical** — hand-curated nodes live in a re-runnable seed script; the JSON is
  the evolving state. Append new nodes; do not blind-re-seed if the live graph holds `add-finding`
  deltas the seed doesn't.
- **The thesis is an attribute** (`strategic_fit`), not structure.

## Porting

Domain-**invariant** (copy verbatim): the schema, the four-mode logic, the loop, the invariants.
Domain-**specific** (tune in `GraphConfig`): the status ladder (`proven`/`refuted` sets), the
decision weights, the node `kind` names, and the abduction thresholds. The LLM stays out of
deduction and decision.

```python
from reasongraph import GraphConfig, ReasonGraph
cfg = GraphConfig(
    proven=frozenset({"validated", "shipped"}),     # your evidence ladder
    refuted=frozenset({"killed"}),
    weights=dict(payoff=.30, centrality=.20, tract=.15, readiness=.10, fit=.10, info=.10, risk=.05),
)
ReasonGraph.from_file("roadmap.json", cfg).report()
```

**Failure modes to avoid:** an LLM in the deterministic modes (non-reproducible rankings); a blind
re-seed (clobbers live evidence); confidence not capped by evidence (rewards assertion over proof);
dropping negative results (the frontier stops evolving); ignoring centrality (you chase leaves and
never unblock the graph).

## Worked example

`examples/governed_innovation.py` builds a small governed-agentic-innovation graph and runs one
pass. With zero hand-ranking the engine: marks `T-INDEX` and `T-BUDGET-SPLIT` **READY** (their
prerequisites are proven), `T-PREEMPT` **AWAITING** (it needs `T-INDEX`), and
`T-AUTONOMOUS-OUTER` **BLOCKED** (it depends on the refuted `F-NAIVE-OUTER`); ranks the frontier;
flags the externally-supported finding as a "generalize?" candidate; and emits abduction tasks —
including a *repair* task for the blocked target that points straight at the `T-BUDGET-SPLIT`
reroute. Run it, then `reasongraph add-finding ... T-INDEX proven` and watch `T-PREEMPT` become
ready.
