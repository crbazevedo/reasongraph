# reasongraph

**A reasoning engine for principled, evidence-evolving programmes — the governed outer-loop for
agentic innovation.**

Most roadmaps are prose, so they rot: a result lands and "what's next" needs a human to re-read
everything. `reasongraph` makes the roadmap a **typed graph of claims** (proven / refuted / open)
and runs **Peirce's inference triad plus a decision layer** over it — so the system tells you what
is *now reachable*, what just *broke*, what *generalizes*, what new *hypothesis* a surprise demands,
and what to *do next* — auditably, every cycle. Negative results are first-class fuel, not failures.

It is ~150 lines of standard-library Python. No dependencies. An LLM enters only the two
*generative* modes; the rest is pure and reproducible.

## Why "the governed outer-loop"

An agentic system has two regimes. An **inner loop** executes directed work under an inherited
authority profile (bounded downside). An **outer loop** decides *what to pursue when nothing is
asking* — it sets the agenda, and its downside is unbounded. Governing that outer loop well is the
hard, under-served problem.

`reasongraph` *is* a governed outer-loop: a disciplined way to choose the next move over a body of
interdependent claims, evolve on evidence, and keep every decision explainable. Use it to steer a
research programme, an innovation portfolio, a security investigation, a migration — any agenda
where the steps depend on each other and the priorities keep changing as results arrive.

## Install

```bash
pip install -e .          # stdlib only; nothing else is pulled in
```

## Quickstart

```bash
python examples/governed_innovation.py            # build a sample graph + run one pass
reasongraph pass examples/governed_innovation.json
reasongraph add-finding examples/governed_innovation.json T-INDEX proven --conf 0.8 --ev proof.md
reasongraph validate examples/governed_innovation.json   # lint the graph (CI-friendly exit code)
reasongraph pass examples/governed_innovation.json --json # machine-readable pass for tooling
reasongraph show examples/governed_innovation.json T-INDEX # one node + its graph context
```

`reasongraph` dogfoods its own roadmap: [`examples/reasongraph_roadmap.py`](examples/reasongraph_roadmap.py)
models the backlog as a reason-graph and lets the engine rank what to build next.

A pass prints four blocks: **DEDUCTION** (ready / blocked), **DECISION** (the ranked frontier),
**INDUCTION** (confidence + generalization flags), **ABDUCTION** (hypothesis tasks for an LLM).

```python
from reasongraph import ReasonGraph
rg = ReasonGraph.from_file("graph.json")
rg.report()                                  # the full pass
rg.add_finding("T-INDEX", "proven", confidence=0.85, evidence="proof.md")   # evolve on a result
```

## The four modes

| Mode | Question | Rule | Deterministic? |
|---|---|---|---|
| **Deduction** | what's *reachable*, what *broke*? | a refuted prerequisite → **BLOCKED**; all prereqs proven → **READY**; one open → **AWAITING** | pure |
| **Induction** | how *confident*, what *generalizes*? | aggregate evidence → confidence; a proven finding with ≥2 (or independent) supports → "generalize?" | rule + LLM |
| **Abduction** | what *hypothesis* does a surprise demand? | emit a task for each *refutation*, *blocked high-payoff target*, or *high-info node*; an LLM writes the new node | LLM |
| **Decision** | what to *do next*? | a transparent weighted score; **unlock-centrality** rewards moves that unblock others; **info-value** rewards results useful *either way* | pure |

```
score = .26·payoff + .20·unlock_centrality + .16·tractability·(1−.5·effort)
      + .12·readiness·ready_bonus + .12·strategic_fit + .12·info_value − .10·risk
```

## The data model

Two arrays in one JSON file. **Nodes** are typed claims: `kind`
(`contribution|finding|target|experiment|hypothesis|reframe`), `status` (the evidence ladder;
`proven`/`refuted` drive the engine), `confidence`, `attrs` (the decision inputs), `evidence[]`
(pointers with polarity), `frontier`. **Edges** have a `relation` that splits three ways:
*prerequisite* (`enables`/`depends-on` → readiness), *negative* (`refutes`/`tensions-with` →
blocking + abduction), and *semantic* (`supports`/`generalizes`/`abduced-from`). See
[docs/SCHEMA.md](docs/SCHEMA.md).

## The live loop

```
run a pass → pick the top action → execute it → add-finding (positive OR negative)
           → run the abduction pass (an LLM turns the emitted tasks into new nodes) → repeat
```

## Design philosophy

- **Negative results are fuel.** A refutation propagates (blocks dependents), prunes (off the
  frontier), and *spawns* (an abduction task that births a reframe). The frontier keeps evolving.
- **Confidence is capped by evidence quality.** You can't game the ranking by asserting confidence.
- **The LLM never scores or decides.** It only proposes new nodes from surprises — so the ranking
  stays reproducible.
- **The thesis is an attribute** (`strategic_fit`). Re-pointing the programme re-weights; it never
  requires a rewrite.

## Porting to your domain

The schema, the four modes, the loop, and the invariants are domain-invariant — copy them. Tune
three things in `GraphConfig`: the **status ladder** (your evidence stages), the **decision
weights** (your priorities), and the **kind** names (your cast). Full guide:
[docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## License

MIT.
