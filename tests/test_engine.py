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


def test_validate_clean_graph_has_no_errors():
    issues = ReasonGraph(_graph()).validate()
    assert [i for i in issues if i["severity"] == "error"] == []


def test_validate_catches_dangling_unknown_and_duplicate():
    g = new_graph(thesis="bad")
    g["nodes"] += [
        make_node("D", "contribution", "dup", "proven"),
        make_node("D", "widget", "dup again", "prooven"),     # duplicate id + unknown kind/status
    ]
    g["edges"] += [make_edge("D", "GHOST", "enables")]         # dangling 'to'
    issues = ReasonGraph(g).validate()
    codes = {i["code"] for i in issues}
    assert "duplicate-id" in codes
    assert "dangling-edge" in codes
    assert "unknown-kind" in codes and "unknown-status" in codes
    # dangling edge is an error -> non-empty error set
    assert any(i["severity"] == "error" and i["code"] == "dangling-edge" for i in issues)


def test_validate_detects_prerequisite_cycle():
    g = new_graph(thesis="cycle")
    g["nodes"] += [
        make_node("A", "target", "a", "open"),
        make_node("B", "target", "b", "open"),
        make_node("C", "target", "c", "open"),
    ]
    g["edges"] += [
        make_edge("A", "B", "enables"),
        make_edge("B", "C", "enables"),
        make_edge("C", "A", "enables"),   # closes the loop
    ]
    issues = ReasonGraph(g).validate()
    assert any(i["code"] == "prereq-cycle" and i["severity"] == "error" for i in issues)


def test_validate_is_deterministic():
    g = _graph()
    a = ReasonGraph(g).validate()
    b = ReasonGraph(g).validate()
    assert a == b


def test_pass_data_is_json_serializable_and_deterministic():
    import json
    rg = ReasonGraph(_graph())
    a = rg.pass_data()
    b = rg.pass_data()
    assert a == b                                       # deterministic
    json.dumps(a)                                       # serializable (no sets / tuples leaking)
    assert a["deduction"]["ready"] == ["T-READY"]
    assert a["deduction"]["proven"] == sorted(a["deduction"]["proven"])   # sets -> sorted lists
    assert a["decision"][0]["node"] == "T-READY"        # ranking matches decision()
    assert a["decision"][0]["readiness"] == "ready"


def test_node_view_reports_context_and_score():
    rg = ReasonGraph(_graph())
    v = rg.node_view("T-WAIT")
    assert v["classification"] == "awaiting"
    assert [p["id"] for p in v["prerequisites"]] == ["T-READY"]
    assert v["frontier"] is True and v["score"] is not None
    # a blocked node names its refuted prerequisite among negatives/prereqs
    vb = rg.node_view("T-BLOCK")
    assert vb["classification"] == "blocked"
    assert "F-BAD" in [p["id"] for p in vb["prerequisites"]]


def test_node_view_unknown_raises():
    try:
        ReasonGraph(_graph()).node_view("NOPE")
        assert False, "expected KeyError"
    except KeyError:
        pass


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
