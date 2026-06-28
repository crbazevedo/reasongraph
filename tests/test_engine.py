"""Deterministic tests for the parts that MUST be reproducible: deduction + decision + evolution.
Run: python -m pytest tests/  (or: python tests/test_engine.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reasongraph import A, make_node, make_edge, new_graph, ReasonGraph  # noqa: E402


def _graph():
    g = new_graph(thesis="test")
    g["nodes"] += [
        make_node("C1", "contribution", "proven block", "proven", attrs=A(payoff=.5)),
        make_node("F-BAD", "finding", "a refuted approach", "refuted", attrs=A(info=.8)),
        make_node("T-READY", "target", "ready target", "open", attrs=A(payoff=.9, info=.8)),
        make_node("T-WAIT", "target", "awaiting target", "open", attrs=A(payoff=.6)),
        make_node("T-BLOCK", "target", "blocked target", "open", attrs=A(payoff=.7)),
    ]
    g["edges"] += [
        make_edge("C1", "T-READY", "enables"),       # T-READY's only prereq is proven -> READY
        make_edge("T-READY", "T-WAIT", "enables"),   # T-WAIT depends on an open target -> AWAITING
        make_edge("F-BAD", "T-BLOCK", "enables"),    # T-BLOCK depends on a refuted node -> BLOCKED
    ]
    return g


def test_deduction_classifies_readiness():
    d = ReasonGraph(_graph()).deduction()
    assert "T-READY" in d["ready"]
    assert "T-WAIT" in d["awaiting"] and d["awaiting"]["T-WAIT"] == ["T-READY"]
    assert "T-BLOCK" in d["blocked"] and d["blocked"]["T-BLOCK"] == ["F-BAD"]
    assert "C1" in d["proven"] and "F-BAD" in d["refuted"]


def test_decision_is_deterministic_and_orders_ready_first():
    rg = ReasonGraph(_graph())
    r1 = rg.decision(rg.deduction())
    r2 = rg.decision(rg.deduction())
    assert [x[1] for x in r1] == [x[1] for x in r2]           # reproducible
    top = r1[0][1]
    assert top == "T-READY"                                   # high payoff + READY bonus wins


def test_add_finding_propagates_and_unblocks():
    rg = ReasonGraph(_graph())
    # proving T-READY should turn its dependent T-WAIT from awaiting -> ready
    rg.add_finding("T-READY", "proven", confidence=0.9)
    d = rg.deduction()
    assert "T-WAIT" in d["ready"]
    # proven nodes leave the frontier
    assert rg.N["T-READY"]["frontier"] is False


def test_abduction_emits_for_surprises():
    triggers = {t["trigger"] for t in ReasonGraph(_graph()).abduction(ReasonGraph(_graph()).deduction())}
    assert "refutation" in triggers       # F-BAD is refuted
    assert "blocked-goal" in triggers     # T-BLOCK is a blocked high-payoff target
    assert "high-info" in triggers        # T-READY has info_value >= 0.7


def test_unknown_node_add_finding_raises():
    try:
        ReasonGraph(_graph()).add_finding("NOPE", "proven")
        assert False, "expected KeyError"
    except KeyError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
