"""Schema + tunable config for a reason-graph.

A reason-graph is two arrays — `nodes` (typed claims) and `edges` (typed links) — in one JSON
file. This module defines the default vocabularies and a `GraphConfig` you tune to your domain
(status ladder, edge semantics, decision weights). Everything here is data; the inference lives
in `engine.py`.

To port to a new domain you usually change only:
  * the status ladder (PROVEN / REFUTED sets),
  * the decision weights, and
  * the node `kind` names.
The four inference modes are domain-invariant.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# The on-disk graph schema. Bumped only on a BREAKING change to the graph format; all additive
# feature work keeps this stable so existing graphs keep loading. `migrate` upgrades older graphs.
SCHEMA_VERSION = "reasongraph/v1"

# ---- default vocabularies (override per domain via GraphConfig) ----
KINDS = ("contribution", "finding", "target", "experiment", "hypothesis", "reframe")
STATUSES = ("open", "in-progress", "proven", "empirical-supported", "empirical-thin",
            "refuted", "conjectural", "deprecated")

PROVEN = frozenset({"proven", "empirical-supported"})   # counts as a satisfied prerequisite
REFUTED = frozenset({"refuted", "deprecated"})           # blocks dependents; triggers abduction
THIN = frozenset({"empirical-thin"})                     # supported but confidence-capped

PREREQ_REL = frozenset({"enables", "depends-on"})        # drive readiness (deduction)
NEG_REL = frozenset({"refutes", "tensions-with"})        # drive blocking + abduction
SEMANTIC_REL = frozenset({"supports", "generalizes", "validated-by", "abduced-from"})  # lineage
# any relation outside the three groups above is unknown to the engine (validate flags it).

# decision weights: positive terms ~sum to 1; risk subtracts.
DEFAULT_WEIGHTS = dict(payoff=.26, centrality=.20, tract=.16, readiness=.12, fit=.12, info=.12, risk=.10)

# evidence whose pointer contains any of these (case-insensitive substring) counts as "independent"
INDEPENDENT_EVIDENCE_HINTS = ("external", "independent", "holdout", "replication", "third-party")


@dataclass(frozen=True)
class GraphConfig:
    """Everything domain-specific about the engine, in one tunable object."""
    proven: frozenset = PROVEN
    refuted: frozenset = REFUTED
    thin: frozenset = THIN
    prereq_rel: frozenset = PREREQ_REL
    neg_rel: frozenset = NEG_REL
    semantic_rel: frozenset = SEMANTIC_REL
    kinds: frozenset = frozenset(KINDS)            # validate: flag node kinds outside this set
    statuses: frozenset = frozenset(STATUSES)      # validate: flag statuses outside this ladder
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    ready_bonus: tuple = (1.0, 0.6, 0.2)        # ready / awaiting / else
    payoff_default: float = 0.4                 # assumed payoff of an unscored downstream node
    independent_hints: tuple = INDEPENDENT_EVIDENCE_HINTS
    blocked_payoff_min: float = 0.6             # abduction: only repair blocked targets at/above this
    high_info_min: float = 0.7                  # abduction: enumerate outcomes for nodes at/above this
    generalize_support_min: int = 2             # induction: generalize a finding with >= this many supports
    prior_weight: float = 2.0                   # subjective-logic: non-informative prior weight W
    base_rate: float = 0.5                      # subjective-logic: prior probability a (confidence with no evidence)


def A(payoff=.5, effort=.5, tract=.5, ready=.5, fit=.5, info=.5, risk=.3, **extra):
    """Build a node's decision attributes (all in [0,1]). Extra keys (venue, tags...) pass through."""
    d = dict(payoff=payoff, effort=effort, tractability=tract, readiness=ready,
             strategic_fit=fit, info_value=info, risk=risk)
    d.update(extra)
    return d


def make_node(id, kind, title, status, *, confidence=0.5, attrs=None, statement="",
              evidence=None, frontier=None):
    """Construct a node. `frontier` defaults to True for open targets/experiments."""
    if frontier is None:
        frontier = (kind in ("target", "experiment") and status == "open")
    return dict(id=id, kind=kind, title=title, statement=statement, status=status,
                confidence=confidence, attrs=attrs if attrs is not None else A(),
                evidence=evidence or [], frontier=frontier)


def make_edge(frm, to, relation, weight=1.0):
    return {"from": frm, "to": to, "relation": relation, "weight": weight}


def new_graph(thesis="", **meta):
    """An empty graph with a meta block. `thesis` is shown in the report header and is the
    natural place to encode 'what this programme is currently about' (re-pointable via attrs)."""
    m = dict(schema=SCHEMA_VERSION, thesis=thesis)
    m.update(meta)
    return dict(meta=m, nodes=[], edges=[])
