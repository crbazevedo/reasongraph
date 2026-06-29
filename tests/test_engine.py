"""Deterministic tests for the parts that MUST be reproducible: deduction + decision + evolution.
Run: python -m pytest tests/  (or: python tests/test_engine.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reasongraph import A, make_node, make_edge, new_graph, ReasonGraph, GraphConfig  # noqa: E402


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


def _chain():
    """P (refuted) -> C -> GC : a two-deep prerequisite chain under a refutation."""
    g = new_graph(thesis="transitive block")
    g["nodes"] += [
        make_node("P", "finding", "refuted premise", "refuted"),
        make_node("C", "target", "child of P", "open", attrs=A(payoff=.6)),
        make_node("GC", "target", "grandchild of P", "open", attrs=A(payoff=.6)),
    ]
    g["edges"] += [make_edge("P", "C", "enables"), make_edge("C", "GC", "enables")]
    return g


def test_block_propagates_transitively():
    d = ReasonGraph(_chain()).deduction()
    assert "C" in d["blocked"] and d["blocked"]["C"] == ["P"]
    assert "GC" in d["blocked"]            # transitive: BLOCKED via its blocked parent (was AWAITING)
    assert d["blocked"]["GC"] == ["C"]     # cause names the immediate dead prerequisite
    assert "GC" not in d["awaiting"]


def test_transitive_block_recovers_when_root_is_overturned():
    rg = ReasonGraph(_chain())
    rg.add_finding("P", "proven")          # overturn the root refutation
    d = rg.deduction()
    # the block is lifted across the subgraph: C is now READY (P proven), GC AWAITS C being proven
    assert "C" in d["ready"]
    assert "GC" in d["awaiting"] and d["awaiting"]["GC"] == ["C"]
    assert "C" not in d["blocked"] and "GC" not in d["blocked"]
    # ...and proving C cascades GC to READY
    rg.add_finding("C", "proven")
    assert "GC" in rg.deduction()["ready"]


def test_blocking_causes_traces_root_refutation():
    rg = ReasonGraph(_chain())             # P (refuted) -> C -> GC
    assert rg.blocking_causes("C") == ["P"]
    assert rg.blocking_causes("GC") == ["P"]     # traced through the blocked intermediate C
    assert rg.blocking_causes("P") == []         # P itself is refuted, not blocked


def test_node_view_reports_root_blocked_by():
    v = ReasonGraph(_chain()).node_view("GC")
    assert v["classification"] == "blocked"
    assert v["blocked_by"] == ["P"]              # names the root cause, not the immediate parent C


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
    # proven nodes leave the frontier (derived, not a mutated stamp)
    assert rg.is_frontier(rg.N["T-READY"]) is False
    assert "T-READY" not in [i for _, i, *_ in rg.decision(d)]


def test_frontier_membership_recovers_when_a_finding_is_overturned():
    """The T-STATUS-DERIVED contract: refute a frontier target then overturn it, and it returns
    to the decision ranking — frontier is derived from status, not a one-way stamp."""
    rg = ReasonGraph(_graph())
    assert "T-READY" in [i for _, i, *_ in rg.decision(rg.deduction())]
    rg.add_finding("T-READY", "refuted")
    assert "T-READY" not in [i for _, i, *_ in rg.decision(rg.deduction())]
    rg.add_finding("T-READY", "open")                      # overturn the refutation
    assert "T-READY" in [i for _, i, *_ in rg.decision(rg.deduction())]   # recovered
    assert rg.is_frontier(rg.N["T-READY"]) is True


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


def test_export_mermaid_and_dot_are_deterministic_and_status_colored():
    rg = ReasonGraph(_graph())
    m1, m2 = rg.to_mermaid(), rg.to_mermaid()
    assert m1 == m2 and m1.startswith("flowchart TD")    # deterministic
    assert ":::proven" in m1 and ":::refuted" in m1 and ":::ready" in m1   # status classes applied
    assert "classDef proven" in m1
    dot = rg.to_dot()
    assert dot.startswith("digraph reasongraph") and dot.rstrip().endswith("}")
    assert '"C1" -> "T-READY"' in dot                    # prerequisite edge rendered
    assert "fillcolor" in dot                            # nodes status-filled


def test_abduce_payload_carries_tasks_and_contract():
    import json
    rg = ReasonGraph(_graph())                          # F-BAD refuted -> a refutation task exists
    payload = json.loads(rg.abduce_payload())
    assert "instructions" in payload and "tasks" in payload
    assert any(t["trigger"] == "refutation" and t["node"] == "F-BAD" for t in payload["tasks"])
    assert rg.abduce_payload() == rg.abduce_payload()   # deterministic


def test_ingest_abduced_appends_node_and_lineage_edge():
    rg = ReasonGraph(_graph())
    added, rejected = rg.ingest_abduced([
        {"abduced_from": "F-BAD", "id": "R-FIX", "kind": "reframe",
         "title": "a repair", "statement": "weaker-but-true claim"},
    ])
    assert added == ["R-FIX"] and rejected == []
    n = rg.N["R-FIX"]
    assert n["status"] == "conjectural" and rg.is_frontier(n) is True
    # lineage edge R-FIX --abduced-from--> F-BAD
    assert any(e["from"] == "R-FIX" and e["to"] == "F-BAD" and e["relation"] == "abduced-from"
               for e in rg.g["edges"])


def test_ingest_abduced_is_firewalled_from_scoring():
    """The LLM proposes structure only: any attrs/score it sends are ignored — neutral defaults win."""
    rg = ReasonGraph(_graph())
    rg.ingest_abduced([{"abduced_from": "F-BAD", "id": "H-X", "kind": "hypothesis",
                        "title": "h", "attrs": {"payoff": 1.0, "info_value": 1.0}, "confidence": 0.99}])
    a = rg.N["H-X"]["attrs"]
    assert a["payoff"] == 0.5 and a["info_value"] == 0.5   # default A(), NOT the LLM's 1.0
    assert rg.N["H-X"]["confidence"] == 0.5


def test_ingest_abduced_rejects_bad_proposals():
    rg = ReasonGraph(_graph())
    added, rejected = rg.ingest_abduced([
        {"abduced_from": "F-BAD", "id": "C1", "kind": "reframe", "title": "dup id"},      # exists
        {"abduced_from": "GHOST", "id": "R-OK", "kind": "reframe", "title": "dangling src"},
        {"abduced_from": "F-BAD", "kind": "reframe", "title": "no id"},                   # missing id
    ])
    assert added == []
    reasons = {p.get("id", "?"): why for p, why in rejected}
    assert "C1" in reasons and "R-OK" in reasons and "?" in reasons
    assert ReasonGraph(rg.g).validate() == ReasonGraph(_graph()).validate()  # graph unharmed (no dangling)


def test_weight_sensitivity_deterministic_and_covers_all_weights():
    rg = ReasonGraph(_graph())
    a, b = rg.weight_sensitivity(), rg.weight_sensitivity()
    assert a == b                                                   # deterministic
    assert {p["weight"] for p in a["perturbations"]} == set(rg.cfg.weights)
    assert len(a["perturbations"]) == 2 * len(rg.cfg.weights)       # ± per weight
    assert a["baseline_top"] == a["baseline"][0]


def test_weight_sensitivity_flags_unstable_top():
    # A wins on payoff, B wins on info, tuned so a ±20% weight shift crosses the tie.
    g = new_graph(thesis="near-tie")
    g["nodes"] += [
        make_node("A", "target", "a", "open", attrs=A(payoff=.8, info=.0)),
        make_node("B", "target", "b", "open", attrs=A(payoff=.3, info=.975)),
    ]
    rep = ReasonGraph(g).weight_sensitivity(0.2)
    assert rep["baseline_top"] == "A"
    assert any(p["top_changed"] for p in rep["perturbations"])      # some ±20% flips the top
    assert "A" in rep["fragile_nodes"] and "B" in rep["fragile_nodes"]


def test_weight_sensitivity_stable_when_dominant():
    g = new_graph(thesis="dominant")
    g["nodes"] += [
        make_node("A", "target", "a", "open", attrs=A(payoff=.9, info=.9, tract=.9, ready=.9, fit=.9)),
        make_node("B", "target", "b", "open", attrs=A(payoff=.1, info=.1, tract=.1, ready=.1, fit=.1, risk=.9)),
    ]
    rep = ReasonGraph(g).weight_sensitivity(0.2)
    assert rep["baseline_top"] == "A"
    assert not any(p["top_changed"] for p in rep["perturbations"])  # A dominates every dimension
    assert rep["fragile_nodes"] == []


def test_custom_config_ports_status_ladder_without_engine_changes():
    """Portability: a domain-tuned GraphConfig (the only porting surface) drives the SAME engine —
    here a security-audit ladder where 'confirmed' satisfies and 'false-positive' blocks."""
    cfg = GraphConfig(proven=frozenset({"confirmed"}), refuted=frozenset({"false-positive"}))
    g = new_graph(thesis="ported")
    g["nodes"] += [
        make_node("V", "vuln", "a confirmed vuln", "confirmed"),
        make_node("VF", "vuln", "a false positive", "false-positive"),
        make_node("R", "remediation", "fix for V", "open", attrs=A(payoff=.9), frontier=True),
        make_node("RF", "remediation", "fix for VF", "open", attrs=A(payoff=.9), frontier=True),
    ]
    g["edges"] += [make_edge("V", "R", "enables"), make_edge("VF", "RF", "enables")]
    rg = ReasonGraph(g, cfg)
    d = rg.deduction()
    assert "R" in d["ready"]           # confirmed prereq satisfies -> READY (custom proven set)
    assert "RF" in d["blocked"]        # false-positive prereq blocks -> BLOCKED (custom refuted set)
    assert "R" in [i for _, i, *_ in rg.decision(d)]


def test_cli_load_config_from_file_path():
    from reasongraph.cli import _load_config
    sec = os.path.join(os.path.dirname(__file__), "..", "examples", "security_audit.py")
    cfg = _load_config(sec + ":SEC")                    # loads side-effect-free (build() guarded)
    assert "confirmed" in cfg.proven and "false-positive" in cfg.refuted
    assert _load_config(None) is None                   # no --config -> default engine config


def test_cli_load_config_rejects_bad_spec():
    from reasongraph.cli import _load_config
    for bad in ("nocolon", ":NAME", "module:"):
        try:
            _load_config(bad)
            assert False, f"expected ValueError for {bad!r}"
        except ValueError:
            pass


def test_cli_pass_honors_config_end_to_end():
    """A ported graph passed via the CLI with --config classifies under its own ladder."""
    from reasongraph.engine import save
    cfg = _make_security_cfg()
    g = new_graph(thesis="cli-config e2e")
    g["nodes"] += [
        make_node("V", "vuln", "confirmed", "confirmed"),
        make_node("R", "remediation", "fix", "open", attrs=A(payoff=.9), frontier=True),
    ]
    g["edges"] += [make_edge("V", "R", "enables")]
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        save(g, fh.name)
        path = fh.name
    rg = ReasonGraph.from_file(path, cfg)
    assert "R" in rg.deduction()["ready"]               # confirmed prereq -> ready under the ported cfg
    os.remove(path)


def _make_security_cfg():
    return GraphConfig(proven=frozenset({"confirmed", "deployed"}),
                       refuted=frozenset({"false-positive", "risk-accepted"}))


def test_legacy_graph_loads_and_runs_without_optional_keys():
    """Backward compatibility: a v1 graph missing optional node keys (attrs/evidence/confidence)
    still loads and runs every mode — the engine reads optional fields defensively."""
    import json
    g = {"meta": {"schema": "reasongraph/v1", "thesis": "legacy"},
         "nodes": [{"id": "A", "kind": "target", "title": "a", "status": "open", "frontier": True},
                   {"id": "B", "kind": "contribution", "title": "b", "status": "proven"}],
         "edges": [{"from": "B", "to": "A", "relation": "enables"}]}
    rg = ReasonGraph(g)
    d = rg.deduction()
    assert "A" in d["ready"]                              # B proven -> A ready, despite A lacking attrs
    assert rg.decision(d)[0][1] == "A"                    # decision tolerates missing attrs (defaults)
    assert [i for i in rg.validate() if i["severity"] == "error"] == []
    json.dumps(rg.pass_data())                            # structured views work on a legacy graph too


def test_migrate_backfills_and_is_idempotent():
    g = {"meta": {"thesis": "no schema"},                 # missing meta.schema + node attrs/evidence
         "nodes": [{"id": "A", "kind": "target", "title": "a", "status": "open", "frontier": True}],
         "edges": []}
    rg = ReasonGraph(g)
    changes = rg.migrate()
    assert any("schema" in c for c in changes)
    assert rg.N["A"]["attrs"] and rg.N["A"]["evidence"] == []   # backfilled
    assert rg.g["meta"]["schema"] == "reasongraph/v1"
    assert rg.migrate() == []                             # idempotent: a second run is a no-op
    # migration is non-destructive: the original claim is untouched
    assert rg.N["A"]["title"] == "a" and rg.N["A"]["status"] == "open"


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
