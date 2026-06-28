# Data model

One JSON file, two arrays — `nodes` and `edges` — plus a `meta` block. This is the live state; a
re-runnable seed script is the canonical source (see METHODOLOGY → invariants).

## meta
```json
{ "schema": "reasongraph/v1", "thesis": "what this programme is currently about" }
```
`thesis` is shown in the report header; re-pointing the programme is a re-weight (`strategic_fit`),
not a rewrite.

## node
```json
{
  "id": "T-INDEX",
  "kind": "target",
  "title": "one-line label",
  "statement": "the precise claim / what proving it means",
  "status": "open",
  "confidence": 0.5,
  "attrs": { "payoff":0.9, "effort":0.5, "tractability":0.6, "readiness":0.8,
             "strategic_fit":0.95, "info_value":0.8, "risk":0.35 },
  "evidence": ["path/to/proof_or_data", "external-benchmark: ...", "free-text provenance"],
  "frontier": true
}
```

| field | meaning |
|---|---|
| `kind` | `contribution` (building block) · `finding` (accumulated result, +/−) · `target` (open claim) · `experiment` (open data-gathering) · `hypothesis` / `reframe` (LLM-abduced) |
| `status` | `open · in-progress · proven · empirical-supported · empirical-thin · refuted · conjectural · deprecated`. The engine only cares about two sets: **PROVEN** = {proven, empirical-supported} and **REFUTED** = {refuted, deprecated}. |
| `confidence` | [0,1]; set by induction, capped by evidence quality |
| `attrs` | the decision inputs, all [0,1]: `payoff`, `effort`, `tractability`, `readiness`, `strategic_fit` (thesis alignment), `info_value` (decision-useful either way), `risk`. Extra keys (e.g. `venue`, tags) pass through untouched. |
| `evidence` | pointers *with polarity* — a path to a proof/dataset, or a provenance string. Count + independence drive induction. |
| `frontier` | is it an actionable next target? (auto-true for open targets/experiments; false once proven/refuted) |

## edge
```json
{ "from": "C-SUBSTRATE", "to": "T-INDEX", "relation": "enables", "weight": 1.0 }
```

`relation` splits three ways:

| group | relations | effect |
|---|---|---|
| **prerequisite** | `enables`, `depends-on` | drive readiness (deduction) — a refuted prerequisite blocks the dependent |
| **negative** | `refutes`, `tensions-with` | flag conflict; feed abduction context |
| **semantic** | `supports`, `generalizes`, `validated-by`, `abduced-from` | lineage / support links |

All vocabularies (status sets, prerequisite/negative relations, decision weights, abduction
thresholds) live in `GraphConfig` and are overridable per domain — see METHODOLOGY → porting.
