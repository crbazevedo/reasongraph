# Changelog

All notable changes to `reasongraph` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project follows [Semantic
Versioning](https://semver.org/): pre-1.0, **MINOR** = new features, **PATCH** = fixes; the **graph
schema** version (`meta.schema`) is bumped only on a breaking change to the on-disk format and has
its own upgrade path (`reasongraph migrate`). See [docs/UPGRADING.md](docs/UPGRADING.md).

## [Unreleased]

### Added
- **Subjective-logic confidence** — `ReasonGraph.opinion(node)` derives an opinion
  (belief / disbelief / uncertainty / projected confidence) from a node's `evidence[]` in closed
  form: `confidence = (r + a·W)/(r+s+W)`. With no evidence, confidence equals the base rate and
  uncertainty is 1 — confidence must be *earned* with evidence, not asserted. Evidence items are
  bare pointers (supporting) or dicts with a `polarity` of `refute`/`challenge`/`against`. Surfaced
  in `show` / `node_view`; tunable via new `GraphConfig.prior_weight` (W) and `base_rate` (a). Pure
  and deterministic; does not change the decision ranking. Backward compatible (string evidence
  counts as supporting).

## [0.2.0] — 2026-06-29

Backward compatible: **existing `reasongraph/v1` graphs load and run unchanged — no migration
required.** Everything below is additive; two deduction *behaviors* changed (see "Changed").

### Added
- **`validate [graph] [--json]`** — a pure graph linter: dangling edges, unknown
  kind/status/relation, attrs out of `[0,1]`, self-edges, duplicate/missing ids, and **prerequisite
  cycles**. Exits non-zero on any error, so it doubles as a CI gate.
- **`pass --json`** and **`show <node> [--json]`** — structured pass output and a single-node view
  (prereqs / dependents / classification / score / root cause) for tooling.
- **`export [graph] --mermaid|--dot`** — status-colored graph visualization.
- **`abduce [graph] --run "<cmd>" [--dry-run]`** — run the abduction pass through an *external* LLM:
  the command receives the emitted tasks and returns proposed nodes, which are validated and written
  back with `abduced-from` edges. The LLM proposes structure only; the engine assigns decision
  attributes (the firewall is preserved).
- **`sensitivity [graph] [--delta] [--json]`** — perturb each decision weight ±delta and report
  whether the top pick or any rank flips.
- **`--config MODULE:NAME`** (or `PATH.py:NAME`) on every graph-reading command — load a domain
  `GraphConfig` so a ported graph (different status ladder / kinds / weights) works end-to-end.
- **`migrate [graph]`** and **`version` / `--version`** — adopter tooling (schema upgrade + version
  reporting).
- **Root-cause blocking** — a `BLOCK` reports the minimal set of refuted ancestors responsible
  (`blocking_causes`, surfaced in `show` and `node_view.blocked_by`).
- **`examples/security_audit.py`** — a second worked example (authorized security audit) proving the
  engine is domain-invariant: only `GraphConfig` and graph content change.
- **`docs/RESEARCH-NOTES.md`** — the literature grounding for the four modes.

### Changed
- **Deduction now propagates `BLOCKED` transitively.** A descendant of a refuted node is `BLOCKED`,
  not `AWAITING` (a real Truth-Maintenance-System invalidation). This re-classifies some nodes in an
  existing graph; the graph file itself is unchanged.
- **Frontier membership is derived, not stamped.** A node leaves the frontier when proven/refuted
  and returns if that finding is later overturned; `add_finding` no longer mutates the `frontier`
  flag. (The engine also now reads optional node fields defensively, so graphs missing `attrs` run.)

### Compatibility
- Graph schema stays **`reasongraph/v1`**. No graph migration is required to adopt 0.2.0.
- `reasongraph migrate` is available to normalize older graphs (stamp `meta.schema`, backfill
  optional keys) and is the seam for any future schema change. It is idempotent and non-destructive.

## [0.1.0] — initial release

The core engine: a typed claim graph + Peirce's triad (deduction / induction / abduction) + a
deterministic decision layer; `GraphConfig`; the `pass` and `add-finding` CLI; the
`governed_innovation` worked example; README / METHODOLOGY / SCHEMA docs.
