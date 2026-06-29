"""Command-line interface.

    reasongraph pass [graph.json] [--log decision_log.md] [--json]
    reasongraph show <graph.json> <node-id> [--json]
    reasongraph export [graph.json] [--mermaid|--dot]
    reasongraph abduce [graph.json] [--run "<llm-cmd>"] [--dry-run]
    reasongraph sensitivity [graph.json] [--delta 0.2] [--json]
    reasongraph add-finding <graph.json> <node-id> <status> [--conf C] [--note "..."] [--ev PTR]
    reasongraph validate [graph.json] [--json]

`pass` runs deduction + induction + abduction + the ranked frontier (and optionally appends a
decision-log line); `--json` emits the whole pass as a machine-readable object instead.
`show` prints one node plus its graph context (prereqs / dependents / classification / score).
`add-finding` records a result on an existing node — positive OR negative, both first-class — saves,
and re-runs the pass (frontier membership is *derived* from status, so a proven/refuted node leaves
the frontier and returns if the finding is later overturned). `validate` lints the
graph (dangling edges, unknown status/kind/relation, prerequisite cycles); it exits non-zero if
any *error*-severity issue is found, so it doubles as a CI gate.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from .engine import ReasonGraph, save


def _load_config(spec):
    """Resolve --config 'MODULE:NAME' or 'PATH.py:NAME' to a GraphConfig (or None). Lets a ported
    graph carry its own status ladder / kinds / weights so every CLI command behaves correctly."""
    if not spec:
        return None
    import importlib
    import importlib.util
    target, sep, name = spec.rpartition(":")
    if not sep or not target or not name:
        raise ValueError(f"--config must be MODULE:NAME or PATH.py:NAME, got '{spec}'")
    if target.endswith(".py") or os.sep in target:
        ms = importlib.util.spec_from_file_location("_rg_cfg", target)
        if ms is None:
            raise ValueError(f"--config: cannot load file '{target}'")
        mod = importlib.util.module_from_spec(ms)
        ms.loader.exec_module(mod)
    else:
        mod = importlib.import_module(target)
    return getattr(mod, name)


def _format_node(v):
    def refs(items):
        return ", ".join(f"{r['id']}({r.get('status', '?')})" for r in items) or "none"
    L = [f"{v['id']}  [{v['kind']} · {v['status']} · {v['classification']}]",
         f"  {v['title']}"]
    if v.get("statement"):
        L.append(f"  statement: {v['statement']}")
    sc = f"{v['score']}" if v["score"] is not None else "—"
    L += [f"  confidence: {v['confidence']}   frontier: {v['frontier']}   score: {sc}"]
    if v.get("blocked_by"):
        L.append(f"  blocked by (root refutation): {', '.join(v['blocked_by'])}")
    L += [f"  prerequisites: {refs(v['prerequisites'])}",
          f"  negatives:     {refs(v['negatives'])}",
          f"  feeds:         {refs(v['feeds'])}"]
    if v.get("evidence"):
        L.append(f"  evidence: {'; '.join(str(e) for e in v['evidence'])}")
    return "\n".join(L)


def _format_sensitivity(rep):
    pct = int(round(rep["delta"] * 100))
    L = [f"weight-sensitivity (±{pct}%) — baseline top: {rep['baseline_top'] or 'none'}",
         f"  {'weight':12} {'-':>10}  {'+':>10}"]
    by = {}
    for p in rep["perturbations"]:
        by.setdefault(p["weight"], {})[p["sign"]] = p
    for k in sorted(by):
        def cell(sign):
            p = by[k].get(sign)
            if not p:
                return ""
            return (p["top"] + ("*" if p["top_changed"] else "")) if p["top"] else "—"
        L.append(f"  {k:12} {cell('-'):>10}  {cell('+'):>10}")
    flips = sorted({p["weight"] + p["sign"] for p in rep["perturbations"] if p["top_changed"]})
    if flips:
        L.append(f"\n  TOP PICK FLIPS under: {', '.join(flips)}  (* marks a changed top)")
    else:
        L.append(f"\n  top pick is STABLE under every single-weight ±{pct}% perturbation")
    L.append(f"  rank-fragile nodes: {', '.join(rep['fragile_nodes']) or 'none'}")
    return "\n".join(L)


def _abduce(args):
    """Drive an external LLM through one abduction pass: emit tasks -> run the command -> ingest the
    proposed nodes -> validate -> save -> re-run the pass. The LLM stays a black box behind --run."""
    import subprocess
    rg = ReasonGraph.from_file(args.graph, args._cfg)
    payload = rg.abduce_payload()
    if args.dry_run or not args.run:
        print(payload)
        if not args.run and not args.dry_run:
            print("\n(no --run given; pipe the JSON above to an LLM, or pass "
                  '--run "<cmd>" to do it in one step.)', file=sys.stderr)
        return 0
    proc = subprocess.run(args.run, shell=True, input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"--run command failed (exit {proc.returncode}):\n{proc.stderr}", file=sys.stderr)
        return 1
    try:
        proposals = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"could not parse proposals as JSON: {e}\n--- got ---\n{proc.stdout[:500]}", file=sys.stderr)
        return 1
    if isinstance(proposals, dict):                  # tolerate {"proposals":[...]} / {"nodes":[...]}
        proposals = proposals.get("proposals") or proposals.get("nodes") or [proposals]
    added, rejected = rg.ingest_abduced(proposals)
    errors = [i for i in rg.validate() if i["severity"] == "error"]
    if errors:
        print("aborting (not saved): ingest produced validation errors:", file=sys.stderr)
        for i in errors:
            print(f"  [E] {i['code']} {i['where']}: {i['msg']}", file=sys.stderr)
        return 1
    save(rg.g, args.graph)
    print(f"added {len(added)} node(s): {', '.join(added) or 'none'}")
    for p, why in rejected:
        print(f"  rejected {p.get('id', '?')}: {why}")
    print()
    rg.report()
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="reasongraph", description="reason over a claim graph")
    sub = p.add_subparsers(dest="cmd", required=True)

    # shared on every subcommand: load a domain GraphConfig so ported graphs work end-to-end.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=None, metavar="MODULE:NAME",
                        help="load a domain GraphConfig, e.g. examples/security_audit.py:SEC")
    def add(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    pp = add("pass", help="run a reasoning pass (deduction/induction/abduction/decision)")
    pp.add_argument("graph", nargs="?", default="graph.json")
    pp.add_argument("--log", default=None, help="append a top-3 line to this decision log")
    pp.add_argument("--json", action="store_true", help="emit the full pass as JSON for tooling")

    sp = add("show", help="show one node + its graph context (prereqs/dependents/score)")
    sp.add_argument("graph")
    sp.add_argument("node")
    sp.add_argument("--json", action="store_true", help="emit the node view as JSON")

    ep = add("export", help="export a status-colored graph (Mermaid or Graphviz DOT)")
    ep.add_argument("graph", nargs="?", default="graph.json")
    fmt = ep.add_mutually_exclusive_group()
    fmt.add_argument("--mermaid", action="store_const", dest="fmt", const="mermaid")
    fmt.add_argument("--dot", action="store_const", dest="fmt", const="dot")
    ep.set_defaults(fmt="mermaid")

    bp = add("abduce", help="run the abduction pass through an external LLM, write nodes back")
    bp.add_argument("graph", nargs="?", default="graph.json")
    bp.add_argument("--run", default=None,
                    help="shell command that reads the tasks JSON on stdin and returns a proposals "
                         "JSON array on stdout (the LLM stays external)")
    bp.add_argument("--dry-run", action="store_true",
                    help="print the LLM payload (tasks + contract) and exit; run nothing")

    np = add("sensitivity", help="perturb each decision weight ±delta; flag rank flips")
    np.add_argument("graph", nargs="?", default="graph.json")
    np.add_argument("--delta", type=float, default=0.2, help="relative perturbation (default 0.2 = ±20%%)")
    np.add_argument("--json", action="store_true", help="emit the report as JSON")

    af = add("add-finding", help="record a result on a node, then re-run the pass")
    af.add_argument("graph")
    af.add_argument("node")
    af.add_argument("status")
    af.add_argument("--conf", type=float, default=None)
    af.add_argument("--note", default=None)
    af.add_argument("--ev", default=None, help="an evidence pointer (path or provenance string)")

    vp = add("validate", help="lint the graph; exit non-zero on any error-severity issue")
    vp.add_argument("graph", nargs="?", default="graph.json")
    vp.add_argument("--json", action="store_true", help="emit issues as JSON for tooling")

    args = p.parse_args(argv)
    try:
        args._cfg = _load_config(getattr(args, "config", None))
    except Exception as e:
        print(f"--config error: {e}", file=sys.stderr); return 1

    if args.cmd == "pass":
        rg = ReasonGraph.from_file(args.graph, args._cfg)
        if args.json:
            print(json.dumps(rg.pass_data(), indent=1))
        else:
            rg.report(args.log)
    elif args.cmd == "show":
        try:
            view = ReasonGraph.from_file(args.graph, args._cfg).node_view(args.node)
        except KeyError as e:
            print(e); return 1
        if args.json:
            print(json.dumps(view, indent=1))
        else:
            print(_format_node(view))
    elif args.cmd == "export":
        rg = ReasonGraph.from_file(args.graph, args._cfg)
        print(rg.to_dot() if args.fmt == "dot" else rg.to_mermaid())
    elif args.cmd == "abduce":
        return _abduce(args)
    elif args.cmd == "sensitivity":
        rep = ReasonGraph.from_file(args.graph, args._cfg).weight_sensitivity(args.delta)
        if args.json:
            print(json.dumps(rep, indent=1))
        else:
            print(_format_sensitivity(rep))
    elif args.cmd == "add-finding":
        rg = ReasonGraph.from_file(args.graph, args._cfg)
        try:
            rg.add_finding(args.node, args.status, confidence=args.conf, note=args.note, evidence=args.ev)
        except KeyError as e:
            print(e); return 1
        save(rg.g, args.graph)
        print(f"updated {args.node} -> {args.status}. Re-running pass:\n")
        rg.report()
    elif args.cmd == "validate":
        issues = ReasonGraph.from_file(args.graph, args._cfg).validate()
        errors = sum(1 for i in issues if i["severity"] == "error")
        if args.json:
            print(json.dumps(issues, indent=1))
        elif not issues:
            print(f"{args.graph}: ok — no issues")
        else:
            for i in issues:
                mark = "E" if i["severity"] == "error" else "W"
                print(f"  [{mark}] {i['code']:18} {i['where']}: {i['msg']}")
            print(f"\n{errors} error(s), {len(issues) - errors} warning(s)")
        return 1 if errors else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
