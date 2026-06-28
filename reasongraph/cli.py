"""Command-line interface.

    reasongraph pass [graph.json] [--log decision_log.md]
    reasongraph add-finding <graph.json> <node-id> <status> [--conf C] [--note "..."] [--ev PTR]
    reasongraph validate [graph.json] [--json]

`pass` runs deduction + induction + abduction + the ranked frontier (and optionally appends a
decision-log line). `add-finding` records a result on an existing node — positive OR negative,
both first-class — flips it off the frontier if proven/refuted, saves, and re-runs the pass.
`validate` lints the graph (dangling edges, unknown status/kind/relation, prerequisite cycles);
it exits non-zero if any *error*-severity issue is found, so it doubles as a CI gate.
"""
from __future__ import annotations
import argparse
import json
import sys
from .engine import ReasonGraph, save


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="reasongraph", description="reason over a claim graph")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("pass", help="run a reasoning pass (deduction/induction/abduction/decision)")
    pp.add_argument("graph", nargs="?", default="graph.json")
    pp.add_argument("--log", default=None, help="append a top-3 line to this decision log")

    af = sub.add_parser("add-finding", help="record a result on a node, then re-run the pass")
    af.add_argument("graph")
    af.add_argument("node")
    af.add_argument("status")
    af.add_argument("--conf", type=float, default=None)
    af.add_argument("--note", default=None)
    af.add_argument("--ev", default=None, help="an evidence pointer (path or provenance string)")

    vp = sub.add_parser("validate", help="lint the graph; exit non-zero on any error-severity issue")
    vp.add_argument("graph", nargs="?", default="graph.json")
    vp.add_argument("--json", action="store_true", help="emit issues as JSON for tooling")

    args = p.parse_args(argv)

    if args.cmd == "pass":
        ReasonGraph.from_file(args.graph).report(args.log)
    elif args.cmd == "add-finding":
        rg = ReasonGraph.from_file(args.graph)
        try:
            rg.add_finding(args.node, args.status, confidence=args.conf, note=args.note, evidence=args.ev)
        except KeyError as e:
            print(e); return 1
        save(rg.g, args.graph)
        print(f"updated {args.node} -> {args.status}. Re-running pass:\n")
        rg.report()
    elif args.cmd == "validate":
        issues = ReasonGraph.from_file(args.graph).validate()
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
