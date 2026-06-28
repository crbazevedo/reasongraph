# Research notes — the theory under reasongraph

These notes ground reasongraph's four modes in the literature on reasoning and knowledge
representation, and record where the current design is well-founded versus where it makes a naive
simplification worth revisiting. Each "→" line names a backlog node it motivated; those nodes live
in [`examples/reasongraph_roadmap.py`](../examples/reasongraph_roadmap.py) and are ranked by the
engine itself (dogfooding). The deep dives were run as four parallel research passes (2026-06).

The throughline: **reasongraph is, structurally, a bipolar claim–evidence property graph with a
deterministic decision layer.** Its strongest, most defensible choices are (a) the firewall that
keeps the LLM out of deduction/decision and (b) a transparent action-selection layer that classical
reasoning engines lack. Its most exposed simplification is that it propagates *defeat one hop*
instead of computing an argumentation/belief-revision fixpoint with reinstatement.

---

## 1. The inference triad (deduction / induction / abduction)

**Abduction is generation, not justification.** Peirce's schema (CP 5.189) is generative: "The
surprising fact C is observed; but if A were true, C would be a matter of course; hence there is
reason to suspect A is true." The common misreading collapses abduction into Inference to the Best
Explanation (Harman 1965; Lipton 2004), which folds *evaluation* in and is closer to induction
(Campos 2011). reasongraph's hard invariant — the LLM only *proposes* abductive nodes; ranking and
testing live in the deterministic decision/induction layers — is exactly this generation/justification
firewall. This is a feature most systems blur.
→ `F-FIREWALL-GROUNDED` (the invariant is theory-aligned, record it as a finding/reframe).

**What makes an abductive hypothesis "good": consistency, minimality, coverage.** Abductive Logic
Programming frames a solution as a set Δ of abducibles such that the program ∪ Δ explains the
observation, stays consistent, and satisfies integrity constraints (Kakas, Kowalski & Toni 1992).
Cost-based abduction makes this quantitative and is provably equivalent to Bayesian-network MAP
(Charniak & Shimony 1994). Two consequences for reasongraph: rank which surprise to chase partly by
*parsimony* (smaller graph delta preferred); and guard the **"bad lot"** (van Fraassen 1989) — the
best of a poorly-covered hypothesis set is still poor, so track hypothesis *diversity/coverage*, not
just within-set rank.
→ `T-ABDUCE-MINIMALITY`, `T-ABDUCE-COVERAGE`.

**Induction: distinguish enumerative from eliminative support, and name your confirmation measure.**
Goodman's new riddle shows same-form inductions differ in justification, so raw confirming-instance
counts are weak (grue-vulnerable); eliminative support (rivals ruled out) is strong. reasongraph's
`generalize?` flag currently fires on support *count*; it should prefer eliminative breadth. And
"evidence raises confidence" is under-specified until a confirmation measure is fixed (Fitelson 1999,
measure-sensitivity) — commit to the difference measure or log-likelihood-ratio and document it.
→ `T-EVIDENCE-TYPED` (tag evidence enumerative vs eliminative), folded into `T-CONF`.

**The cycle is an economy of research.** Peirce's methodeutic selects the next hypothesis to test by
*cost, value, caution, breadth, incomplexity* — a cost/benefit theory of next-experiment choice that
maps directly onto reasongraph's weighted decision score. Naming the weights after these axes makes
each one defensible.
→ `T-DECISION-ECONOMY` (re-name/justify weights against the methodeutic axes).

*Sources:* Peirce CP 5.189 (via [IEP](https://iep.utm.edu/peir-log/)); [SEP *Abduction*](https://plato.stanford.edu/entries/abduction/);
[Campos 2011](https://link.springer.com/article/10.1007/s11229-009-9709-3);
[Kakas–Kowalski–Toni / ALP overview](https://helios2.mi.parisdescartes.fr/~moraitis/webpapers/abduction-in-logic-programming.pdf);
[Charniak & Shimony 1994](https://www.sciencedirect.com/science/article/abs/pii/0004370294900302);
[SEP *Problem of Induction*](https://plato.stanford.edu/entries/induction-problem/);
[Fitelson 1999](https://fitelson.org/thesis.pdf);
[Peirce & the Economy of Research](https://www.cambridge.org/core/journals/philosophy-of-science/article/abs/peirce-and-the-economy-of-research/17ADDFF39D628594A0683F81E7B9E309).

## 2. Knowledge representation

reasongraph is a **typed property graph** (labels/attrs on nodes and edges; closer to a labeled
property graph than RDF), fused with a **bipolar argumentation framework** and a **claim–evidence
graph**. That fusion is its identity; argumentation theory says it currently under-computes.

- **The prerequisite layer is Datalog/fixpoint deduction.** `enables`/`depends-on` →
  READY/BLOCKED/AWAITING is stratified bottom-up evaluation — well-grounded; frame it as such.
- **Negative edges should compute an argumentation extension.** Dung (1995) abstracts arguments +
  an attack relation and defines acceptability *semantics*: the **grounded extension** is unique,
  polynomial, skeptical — ideal for an auditable engine. reasongraph's `refutes`/`tensions-with` do
  a one-hop block instead. Bipolar AFs (Cayrol & Lagasquie-Schiex 2005) add an independent *support*
  relation — exactly reasongraph's split — and warn that support is **not** the dual of attack
  (so `supports` must declare a reading: deductive / necessary / evidential).
  → `T-GROUNDED-EXTENSION`, `T-SUPPORT-SEMANTICS`.
- **Evidence-with-polarity matches micropublications** (Clark, Ciccarese & Goble 2014): a principal
  claim with a *support graph* and a *challenge graph*, where support is transitive and challenge is
  inferred (undercut vs rebut). reasongraph should distinguish **undercutting** (attack the warrant)
  from **rebutting** (attack the claim), and carry PROV-style source/quality on evidence.
  → folded into `T-CONF` and `T-SUPPORT-SEMANTICS`.
- **Keep the relation ontology small.** The KG/OWL lesson is tractability discipline: 8 edge types
  across 3 families is a good size — any new edge type must map to a computed semantics or it doesn't
  earn its place (an ADR-style fitness check).

*Sources:* [DL Handbook / Baader](https://link.springer.com/chapter/10.1007/978-3-642-23032-5_2);
[Hogan et al. *Knowledge Graphs* 2021](https://arxiv.org/pdf/2003.02320);
[Toulmin model](https://pressbooks.calstate.edu/writingargumentsinstem/chapter/toulmin-argument-model/);
[Dung 1995 semantics overview](https://arxiv.org/html/2202.05506);
[Cayrol & Lagasquie-Schiex 2005](https://www.researchgate.net/publication/220907701);
[Micropublications](https://pmc.ncbi.nlm.nih.gov/articles/PMC4530550/); [PROV-O](https://www.w3.org/TR/prov-o/).

## 3. Inference engines & belief revision

**reasongraph's deduction is a degenerate JTMS** (Doyle 1979): an open node's "justification" is the
conjunction of its prerequisites, and a refuted prerequisite plays the role of an out-list /
contradiction. A correct Truth Maintenance System does more:

- **Transitive invalidation.** A TMS relabels the whole reachable subgraph when support changes.
  **Verified gap:** reasongraph blocks only *immediate* children — a grandchild of a refuted node is
  classified `AWAITING`, not `BLOCKED` (reproduced 2026-06). This is arguably a correctness bug.
  → `F-BLOCK-ONEHOP` (verified finding), `T-BLOCK-TRANSITIVE` (the fix).
- **Recovery when a refutation is overturned.** JTMS relabeling is bidirectional. The clean,
  recovery-by-construction design is **status = pure deterministic function of current evidence,
  recomputed each pass**, never a mutated stamp. This also makes the deduction *non-monotonic in the
  right way* (adding a refutation removes READY; overturning it restores READY) — a feature for a
  roadmap where negative results are first-class. The risk is a *monotonic-by-accident* implementation
  that marks and forgets.
  → `T-STATUS-DERIVED`.
- **OR-support (alternative justifications).** JTMS keeps a node IN if *any* justification is valid;
  ATMS (de Kleer 1986) tracks all minimal supporting assumption-sets. reasongraph's pure-conjunction
  model has no OR: a claim provable two ways would be wrongly BLOCKED if one route is refuted. The
  single most valuable mechanism to import.
  → `T-OR-JUSTIFICATIONS`.
- **Minimal blocking explanation (nogood).** Dependency-directed backtracking names the specific
  assumptions responsible. A BLOCK should carry its *minimal set of refuted ancestors*, not a boolean.
  → `T-BLOCK-EXPLAIN`.
- **Stratification guarantees the determinism.** Datalog forbids a status depending negatively on
  itself through a cycle; that stratification is what actually guarantees a unique fixpoint — the
  property the "deterministic" claim rests on. (reasongraph's new `validate` already flags prerequisite
  cycles — a first step.)
- **Don't pre-optimize.** At tens–hundreds of nodes, full deterministic recomputation each pass is
  the right call; RETE/semi-naive incrementality is premature.

*Sources:* [Doyle 1979 *A TMS*](https://scispace.com/pdf/a-truth-maintenance-system-pim519w5js.pdf);
[de Kleer 1986 *ATMS*](https://www.dbai.tuwien.ac.at/staff/wotawa/atmschapter1.pdf);
[Reiter & de Kleer 1987](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf);
[AGM belief revision (SEP)](https://plato.stanford.edu/entries/logic-belief-revision/);
[Non-monotonic logic (SEP)](https://plato.stanford.edu/archives/fall2016/entries/logic-nonmonotonic/);
[Datalog (stratified negation, semi-naive)](https://en.wikipedia.org/wiki/Datalog).

## 4. Decision & evidence aggregation under uncertainty

**The weighted-sum score is defensible as a transparent screen — name its failure modes.** WSM/SAW
has three pathologies here: (1) *compensation* — a high-payoff node with `readiness≈0` or `risk≈1`
still scores well, though no one would pick a blocked node; (2) *normalization drift* — terms must
share a `[0,1]` scale or weights silently re-rank; (3) *weight non-identifiability* — seven hand-set
weights are unfalsifiable. Determinism-preserving fixes: turn `readiness`/`risk` into a
**non-compensatory eligibility gate** (ELECTRE-style veto) before scoring; make `payoff·readiness`
multiplicative (like the existing `tractability·(1−½·effort)`); and ship a **weight-sensitivity
report** that perturbs each weight ±20% and flags rank flips.
→ `T-NONCOMPENSATORY-GATE`, `T-WEIGHT-SENSITIVITY`.

**"Confidence capped by evidence quality" is literally subjective logic.** An opinion ω=(b,d,u,a)
maps to a Beta distribution from evidence counts: with r supporting and s refuting items,
`confidence = b + a·u = (r + a·W)/(r+s+W)` (W ≈ 2). Thin data forces confidence toward the base rate
a, not toward 1 — a principled, monotone cap with a first-class "I don't know" mass u. Independence
matters: **cumulative fusion** for independent evidence (counts add), **averaging fusion** for
correlated sources (counts don't add → caps confidence). Closed-form and deterministic. Dempster–
Shafer is the wrong tool here (Dempster's rule explodes under conflict — Zadeh 1986).
→ `T-SUBJECTIVE-LOGIC` (the principled basis for `T-CONF`).

**`info_value` can be a real (deterministic) EVPI surrogate.** Expected Value of Perfect Information
is the gain from resolving uncertainty *before acting*; information has value only if it could change
the chosen action — exactly reasongraph's "useful either way." Define a node's info value as the
decision-swing it could cause: `|best_frontier_score_if_resolved_yes − …_if_resolved_no|`, weighted
by current uncertainty. Pure arithmetic over the existing graph — no sampling, no LLM.
→ `T-INFO-EVPI`.

**Truncated 2-hop centrality is Katz-on-a-DAG.** reasongraph's `1-hop + ½·2-hop` *is* Katz centrality
truncated at k=2 with attenuation ½ — deterministic, no eigen-solve, robust to distant churn; its
blind spot is long unlock chains. The clean generalization is *full attenuated DAG reachability*
(`Σ_descendants αᵈᵉᵖᵗʰ·payoff`), computable exactly in one reverse-topological pass, still O(V+E) and
deterministic.
→ `T-CENTRALITY-DAG`.

**Determinism ledger.** All of the above are pure functions of the graph. The ideas that would
*violate* the invariant — Monte-Carlo EVSI, MCMC posteriors, any LLM-scored weight — must stay out of
the decision/induction core (an advisory layer at most).

*Sources:* [Jøsang *Subjective Logic*](https://files.givewell.org/files/labs/AI/Josang2013.pdf);
[Jøsang fusion 2018](https://arxiv.org/pdf/1805.01388);
[Zadeh 1986 on DST](https://www.stat.berkeley.edu/~aldous/Real_World/dempster_shafer.pdf);
[Weighted Sum Model](https://en.wikipedia.org/wiki/Weighted_sum_model);
[EVPI/EVI](https://docs.analytica.com/index.php/Expected_value_of_information_--_EVI,_EVPI,_and_ESVI);
[Saxena & Iyengar, centrality survey](https://arxiv.org/pdf/2011.07190).

---

## How these enter the engine

These are not a separate TODO list — they are nodes in the dogfood graph, ranked by reasongraph
itself. Run `python examples/reasongraph_roadmap.py` then `reasongraph pass
examples/reasongraph_roadmap.json` to see the current ordering. The highest-leverage, most
theoretically-defensible cluster is the belief-revision upgrade (§3): `T-STATUS-DERIVED` +
`T-BLOCK-TRANSITIVE` + `T-OR-JUSTIFICATIONS` + `T-GROUNDED-EXTENSION`, which together move reasongraph
from one-hop defeat to a proper non-monotonic argumentation/TMS fixpoint while preserving the
determinism invariant.
