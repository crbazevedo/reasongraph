"""Command-line interface.

    reasongraph pass [graph.json] [--log decision_log.md]
    reasongraph add-finding <graph.json> <node-id> <status> [--conf C] [--note "..."] [--ev PTR]

`pass` runs deduction + induction + abduction + the ranked frontier (and optionally appends a
decision-log line). `add-finding` records a result on an existing node — positive OR negative,
both first-class — flips it off the frontier if proven/refuted, saves, and re-runs the pass.
"""
from __future__ import annotations
import argparse
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
