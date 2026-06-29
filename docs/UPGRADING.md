# Upgrading reasongraph

This guide is for adopters already using `reasongraph` on a live project. It covers **updating the
install**, **learning what changed**, **using the new features on your existing graph**, and the
**backward-compatibility guarantee**. The per-release detail lives in [CHANGELOG.md](../CHANGELOG.md).

## TL;DR

```bash
pip install --upgrade reasongraph        # or, from a clone:  git pull && pip install -e .
reasongraph version                      # confirm the new version + supported schema
reasongraph validate your_graph.json     # your existing graph keeps working — no migration needed
```

Your graph is **not touched** by upgrading. All 0.2.0 changes are additive; the on-disk schema is
still `reasongraph/v1`.

## 1. Update the installation

- **From PyPI:** `pip install --upgrade reasongraph`
- **From source:** `git pull && pip install -e .` in your clone.
- **Pin a version** in your project if you want reproducibility: `reasongraph==0.2.*`.

Confirm it:

```bash
reasongraph version          # -> reasongraph 0.2.0 (graph schema reasongraph/v1)
reasongraph --version        # same, as a flag
```

## 2. Learn what's new

Read the latest section of [CHANGELOG.md](../CHANGELOG.md). Then try each new command **on your own
graph** — they are all read-only except where noted:

```bash
reasongraph validate your_graph.json            # lint it (CI-friendly exit code)
reasongraph show your_graph.json <NODE-ID>      # one node + its context + root cause of a block
reasongraph pass your_graph.json --json         # structured pass for scripts/dashboards
reasongraph export your_graph.json --mermaid    # paste into any Mermaid renderer (or --dot)
reasongraph sensitivity your_graph.json         # how robust is the top pick to the weights?
reasongraph abduce your_graph.json --dry-run    # see the LLM payload; add --run "<cmd>" to apply
```

Nothing above changes your file (except `abduce --run`, which appends LLM-proposed nodes, and
`add-finding`, which you already use).

## 3. Use the new features on an existing, ongoing project

You do **not** need to rebuild your graph. Concretely:

- **Linting / CI.** Add `reasongraph validate your_graph.json` to your pipeline; it exits non-zero
  on structural errors (dangling edges, prerequisite cycles, …).
- **Tooling / dashboards.** Consume `pass --json` and `show --json` instead of scraping the text
  report.
- **Visualization.** `export --mermaid|--dot` renders your current graph, status-colored.
- **Robustness check.** `sensitivity` tells you whether your decision weights are driving the top
  recommendation or just churning the tail.
- **A non-default domain.** If your programme uses a custom `GraphConfig` (its own status ladder /
  kinds / weights), put it in an importable module and pass it to every command:
  `reasongraph pass your_graph.json --config your_pkg.config:CFG` (or `path/to/config.py:CFG`).
  Previously this only worked from the Python API.

### Two behavior changes to expect

Both improve correctness and need no file change, but your **classifications may shift**:

1. **Transitive blocking.** A node downstream of a refuted prerequisite is now `BLOCKED` (it was
   `AWAITING`). If you tracked "awaiting" counts, expect some to move to "blocked" — that is the fix.
2. **Derived frontier.** A proven/refuted node leaves the frontier automatically and **returns if
   you overturn that finding** (`add-finding ... open`). If you relied on a node staying off the
   frontier after a one-time refutation, it will now reappear when the refutation is lifted.

## 4. Backward-compatibility guarantee

- **The graph schema is versioned** (`meta.schema`, currently `reasongraph/v1`) and is bumped *only*
  on a breaking change to the on-disk format. 0.2.0 did not bump it.
- **Older graphs load and run unchanged.** The engine reads optional node fields (`attrs`,
  `evidence`, `confidence`, `frontier`) defensively, so a graph authored by an earlier version — or
  by hand without every field — works.
- **`reasongraph migrate your_graph.json`** brings an older graph fully up to date in place:
  it stamps `meta.schema` and backfills missing optional keys. It is **idempotent** (safe to re-run)
  and **non-destructive** (never removes, renames, or reinterprets your data, and never fabricates
  `frontier` intent). `validate` will hint when a graph would benefit from it.
- **Semantic versioning.** Pre-1.0: MINOR releases add features and keep graphs compatible; PATCH
  releases fix bugs. A future graph-schema break will arrive as a new schema version with a
  `migrate` path and a prominent CHANGELOG entry — never silently.

## Rollback

If you need to pin back: `pip install reasongraph==0.1.0`. Graphs created or migrated by 0.2.0 remain
`reasongraph/v1` and load under 0.1.0; you simply lose the 0.2.0 commands.
