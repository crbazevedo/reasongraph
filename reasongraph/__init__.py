"""reasongraph — a reasoning engine for principled, evidence-evolving programmes.

A typed graph of claims (proven / refuted / open) with four inference modes over it —
deduction, induction, abduction, decision — that decide *what to tackle next* and *evolve as
evidence (positive or negative) arrives*. ~150 lines of stdlib; an LLM enters only the two
generative modes. See docs/METHODOLOGY.md.
"""
from .schema import GraphConfig, A, make_node, make_edge, new_graph
from .engine import ReasonGraph, load, save

__all__ = ["ReasonGraph", "GraphConfig", "A", "make_node", "make_edge", "new_graph", "load", "save"]
__version__ = "0.1.0"
