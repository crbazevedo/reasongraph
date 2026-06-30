"""The reason-graph inference engine: Peirce's triad + a decision layer.

Four modes (see docs/METHODOLOGY.md):
  DEDUCTION  — deterministic. Propagate proven/refuted along prerequisite edges; classify each
               open node as READY (all prereqs proven), AWAITING (some open), or BLOCKED (a prereq
               refuted). Tells you what is *now reachable* and what just *broke*.
  INDUCTION  — rule (+ an LLM downstream). Aggregate evidence into confidence; flag generalization
               candidates.
  ABDUCTION  — emits hypothesis TASKS for surprises (refutation / blocked-high-payoff / high-info);
               an LLM turns each task into a new node with an `abduced-from` edge.
  DECISION   — deterministic, transparent. Score every frontier node and rank "what to tackle next".

Design rule: the two GENERATIVE modes (abduction, and the generalize flag in induction) only ever
EMIT TASKS (text). The engine never calls an LLM and never uses randomness — DEDUCTION and DECISION
are pure and reproducible. That separation is what keeps the ranking auditable.
"""
from __future__ import annotations
import json
from .schema import GraphConfig, make_node, make_edge


def load(path):
    with open(path) as f:
        return json.load(f)


def save(graph, path):
    with open(path, "w") as f:
        json.dump(graph, f, indent=1)


class ReasonGraph:
    def __init__(self, graph, config=None):
        self.g = graph
        self.cfg = config or GraphConfig()
        self.path = None
        self._index()

    @classmethod
    def from_file(cls, path, config=None):
        rg = cls(load(path), config)
        rg.path = path
        return rg

    def _index(self):
        N = {n["id"]: n for n in self.g["nodes"]}
        pre = {i: [] for i in N}   # prerequisites feeding a node
        out = {i: [] for i in N}   # what a node feeds
        neg = {i: [] for i in N}   # refutes/tensions toward a node
        att = {i: [] for i in N}   # attackers (refutes) toward a node — for the grounded extension
        for e in self.g["edges"]:
            f, t, r = e["from"], e["to"], e["relation"]
            if f not in N or t not in N:
                continue
            if r in self.cfg.prereq_rel:
                pre[t].append(f); out[f].append(t)
            elif r in self.cfg.neg_rel:
                neg[t].append(f); out[f].append(t)
                if r in self.cfg.attack_rel:
                    att[t].append(f)
            else:
                out[f].append(t)
        self.N, self.pre, self.out, self.neg, self.att = N, pre, out, neg, att

    def is_frontier(self, n):
        """Effective frontier membership — a PURE function of authored intent + current status.

        The stored ``frontier`` flag is *intent* ("this is an actionable item"); a node is only
        actually on the frontier while its status is unresolved. Computing this each pass (instead
        of mutating the flag when a finding lands) is what makes recovery automatic: overturning a
        refutation puts the node straight back on the frontier — no mutate-and-forget. See
        docs/RESEARCH-NOTES.md §3 (T-STATUS-DERIVED).
        """
        return bool(n.get("frontier")) and n["status"] not in (self.cfg.proven | self.cfg.refuted)

    # ---------------- ARGUMENTATION (grounded extension) ----------------
    def grounded_extension(self):
        """Dung's grounded labelling over the attack (`refutes`) edges: each node is ``in``
        (justified), ``out`` (defeated by a justified attacker), or ``undec`` (in an unresolved /
        even cycle). Recorded-refuted nodes start defeated, so a refuted attacker cannot defeat its
        target — i.e. *refuting a refuter REINSTATES the original claim*. Pure + deterministic
        (least fixed point of the characteristic function). Returns ``{id: label}``.
        """
        R, att = self.cfg.refuted, self.att
        label = {i: "out" for i, n in self.N.items() if n["status"] in R}   # pre-defeated
        changed = True
        while changed:
            changed = False
            for i in self.N:                                  # accept: all attackers defeated
                if i not in label and all(label.get(a) == "out" for a in att[i]):
                    label[i] = "in"; changed = True
            for i in self.N:                                  # defeat: attacked by a justified node
                if i not in label and any(label.get(a) == "in" for a in att[i]):
                    label[i] = "out"; changed = True
        for i in self.N:
            label.setdefault(i, "undec")                      # left in an even cycle
        return label

    # ---------------- DEDUCTION ----------------
    def deduction(self):
        """Classify every node by propagating proven/refuted along prerequisite edges.

        BLOCKED is TRANSITIVE (TMS-style invalidation, Doyle 1979): a node is blocked if any
        prerequisite is *dead* — refuted OR itself blocked — so a refutation invalidates the whole
        reachable subgraph, not just immediate children. A prerequisite only counts as satisfied
        when PROVEN; an unresolved (ready/awaiting) prerequisite leaves the dependent AWAITING.

        Conflict is resolved by the grounded extension (Dung): an OPEN claim defeated via `refutes`
        edges is treated as refuted (so it blocks dependents), and is REINSTATED when its attacker
        is itself defeated. Recorded proven/refuted status always wins over the structural label.
        Pure + deterministic; memoized DFS with a cycle guard (cycles are reported by `validate`).
        """
        P, R = self.cfg.proven, self.cfg.refuted
        gl = self.grounded_extension()
        proven = {i for i, n in self.N.items() if n["status"] in P}
        refuted = {i for i, n in self.N.items() if n["status"] in R}
        # structural defeat: an open claim that is `out` in the grounded extension blocks dependents.
        refuted |= {i for i, l in gl.items() if l == "out" and i not in proven and i not in refuted}
        state, cause, visiting = {}, {}, set()

        def classify(i):
            if i in proven:
                return "proven"
            if i in refuted:
                return "refuted"
            if i in state:
                return state[i]
            if i in visiting:                 # prerequisite cycle — don't recurse forever
                return "awaiting"
            visiting.add(i)
            dead, pending = [], []
            for p in self.pre[i]:
                ps = classify(p)
                if ps in ("refuted", "blocked"):
                    dead.append(p)
                elif ps != "proven":          # ready/awaiting: present but not yet satisfied
                    pending.append(p)
            visiting.discard(i)
            if dead:
                state[i] = "blocked"; cause[i] = dead
            elif pending:
                state[i] = "awaiting"; cause[i] = pending
            else:
                state[i] = "ready"
            return state[i]

        ready, blocked, awaiting = {}, {}, {}
        for i, n in self.N.items():
            if n["status"] != "open":
                continue
            st = classify(i)
            if st == "blocked":
                blocked[i] = cause[i]
            elif st == "awaiting":
                awaiting[i] = cause[i]
            else:
                ready[i] = True
        return dict(proven=proven, refuted=refuted, ready=ready, blocked=blocked, awaiting=awaiting)

    def blocking_causes(self, i, d=None):
        """The minimal set of REFUTED ancestors responsible for `i` being BLOCKED (the nogood / root
        cause), traced through any intervening blocked prerequisites — dependency-directed, à la a
        TMS. Pure + deterministic; returns [] if `i` is not blocked. `deduction()` reports the
        *immediate* dead prerequisite; this reports the *root* refutation(s) to point at.
        """
        d = d or self.deduction()
        if i not in d["blocked"]:
            return []
        refuted, roots, seen = d["refuted"], set(), set()   # effective: status- OR structurally-defeated
        def walk(j):
            if j in seen:
                return
            seen.add(j)
            for p in self.pre[j]:
                if p in refuted:
                    roots.add(p)
                elif p in d["blocked"]:
                    walk(p)
        walk(i)
        return sorted(roots)

    # ---------------- evidence typing (single source for opinion + induction + views) ----------------
    def _ev_facets(self, e):
        """Normalize one evidence item to its facets. An item is a bare pointer (supporting,
        enumerative, weight 1) or a dict with optional ``polarity`` (support/refute), ``type``
        (enumerative/eliminative), ``independent``, ``weight``, and a ``source``/``ptr`` pointer.
        Independence is also inferred from the pointer text via ``independent_hints``."""
        if isinstance(e, dict):
            pol = str(e.get("polarity", "support")).lower()
            typ = str(e.get("type", e.get("kind", ""))).lower()
            ptr = str(e.get("source") or e.get("ptr") or e.get("id") or "")
            indep = bool(e.get("independent")) or any(h in (ptr + " " + typ).lower()
                                                      for h in self.cfg.independent_hints)
            try:
                w = float(e.get("weight", 1.0))
            except (TypeError, ValueError):
                w = 1.0
            return dict(polarity=("refute" if pol.startswith(("refut", "challeng", "against", "contra"))
                                  else "support"),
                        eliminative=typ.startswith("elim"), enumerative=typ.startswith("enum"),
                        independent=indep, weight=w, ptr=ptr)
        s = str(e)
        return dict(polarity="support", eliminative=False, enumerative=False,
                    independent=any(h in s.lower() for h in self.cfg.independent_hints),
                    weight=1.0, ptr=s)

    def evidence_profile(self, node):
        """Counts of a node's evidence by facet — for induction and the node view. Pure."""
        fs = [self._ev_facets(e) for e in (node.get("evidence") or [])]
        sup = [f for f in fs if f["polarity"] == "support"]
        return dict(support=len(sup), refute=len(fs) - len(sup),
                    eliminative=sum(1 for f in sup if f["eliminative"]),
                    enumerative=sum(1 for f in sup if f["enumerative"]),
                    independent=sum(1 for f in sup if f["independent"]))

    # ---------------- INDUCTION ----------------
    def induction(self, d):
        out = []
        for n in self.g["nodes"]:
            if n["status"] in self.cfg.proven and n["kind"] == "finding":
                p = self.evidence_profile(n)
                strong = p["eliminative"] >= 1 or p["independent"] >= 1   # rivals ruled out / external
                if strong:
                    out.append(("generalize?", n["id"],
                                "eliminative/independent support — propose a generalized claim node"))
                elif p["support"] >= self.cfg.generalize_support_min:
                    out.append(("generalize?", n["id"],
                                "enumerative-only support (Goodman): weak — seek a rival-eliminating "
                                "test before generalizing"))
            if n["status"] in self.cfg.thin:
                out.append(("strengthen", n["id"],
                            "thin evidence — confidence capped until an enabling experiment lands"))
        return out

    def opinion(self, node):
        """A subjective-logic opinion derived from a node's ``evidence[]`` — confidence *capped by
        evidence quality* in closed form (Jøsang). With r supporting and s refuting items, a prior
        weight W and base rate a::

            uncertainty u = W/(r+s+W);  belief b = r/(r+s+W);  disbelief d = s/(r+s+W)
            confidence (projected probability) = b + a*u = (r + a*W)/(r+s+W)

        No evidence ⇒ confidence == the base rate and uncertainty == 1: you cannot assert your way to
        high confidence, it must be earned with evidence. Pure + deterministic. Each evidence item
        contributes its ``weight`` (default 1) to the supporting or refuting tally via ``_ev_facets``
        — so higher-quality / eliminative evidence can be weighted up.
        """
        r = s = 0.0
        for e in (node.get("evidence") or []):
            f = self._ev_facets(e)
            if f["polarity"] == "refute":
                s += f["weight"]
            else:
                r += f["weight"]
        W, a = self.cfg.prior_weight, self.cfg.base_rate
        denom = r + s + W
        b, dd, u = r / denom, s / denom, W / denom
        return dict(support=round(r, 3), refute=round(s, 3), belief=round(b, 3), disbelief=round(dd, 3),
                    uncertainty=round(u, 3), confidence=round(b + a * u, 3))

    # ---------------- ABDUCTION ----------------
    def abduction(self, d):
        tasks = []
        for i in d["refuted"]:
            n = self.N[i]
            tasks.append(dict(trigger="refutation", node=i,
                prompt=(f"REFUTED: {n['title']}. Abduce why it fails and the missing node "
                        "(reframe / weaker-but-true claim / new assumption / repair path) that "
                        "resolves it; add it with an 'abduced-from' edge.")))
        for i, miss in d["blocked"].items():
            if (self.N[i].get("attrs") or {}).get("payoff", 0) >= self.cfg.blocked_payoff_min:
                tasks.append(dict(trigger="blocked-goal", node=i,
                    prompt=(f"BLOCKED high-value target: {self.N[i]['title']} (blocked by refuted "
                            f"{miss}). Abduce a repair path / alternative lemma routing around the "
                            "refuted prerequisite.")))
        for n in self.g["nodes"]:
            if self.is_frontier(n) and (n.get("attrs") or {}).get("info_value", 0) >= self.cfg.high_info_min:
                tasks.append(dict(trigger="high-info", node=n["id"],
                    prompt=(f"HIGH-INFORMATION target {n['id']}: enumerate the 2-3 outcomes "
                            "(positive AND negative) and what each entails downstream, so the "
                            "result is decision-useful either way.")))
        return tasks

    # the LLM contract for `abduce`: an external command reads this on stdin, returns proposals.
    ABDUCE_CONTRACT = (
        "You are the abduction step of a reason-graph. For EACH task below, PROPOSE one new node "
        "(a hypothesis, reframe, weaker-but-true claim, or repair path). "
        "Return ONLY a JSON array; each item is "
        '{"abduced_from": "<the task\'s node id>", "id": "<NEW unique id, e.g. H-... or R-...>", '
        '"kind": "hypothesis" or "reframe", "title": "<short label>", "statement": "<the claim>"}. '
        "Do NOT include scores, confidence, payoff, or any decision attributes — the engine assigns "
        "those. You propose structure only; you never rank.")

    def abduce_payload(self, d=None):
        """Build the stdin payload for an external LLM abduction pass: the emitted hypothesis tasks
        plus the JSON return-contract. Pure — the engine never calls an LLM itself. See
        ingest_abduced() for writing the response back."""
        d = d or self.deduction()
        return json.dumps(dict(instructions=self.ABDUCE_CONTRACT, tasks=self.abduction(d)), indent=1)

    def ingest_abduced(self, proposals):
        """Append LLM-proposed nodes (+ an `abduced-from` lineage edge) to the graph.

        The firewall, enforced here: the LLM proposes STRUCTURE only (id/kind/title/statement); the
        engine assigns NEUTRAL default decision attrs — any attrs/score/confidence in a proposal are
        ignored, so the LLM can never influence the ranking. New nodes enter as `conjectural` and
        on the frontier, to be ranked deterministically next pass. Returns ``(added, rejected)``
        where rejected is a list of ``(proposal, reason)``. Pure w.r.t. external state.
        """
        added, rejected = [], []
        existing = set(self.N)
        for p in proposals if isinstance(proposals, list) else []:
            nid, src = p.get("id"), p.get("abduced_from")
            kind, title = p.get("kind"), p.get("title")
            if not nid or not kind or not title:
                rejected.append((p, "missing id/kind/title")); continue
            if nid in existing:
                rejected.append((p, f"id '{nid}' already exists")); continue
            if src is not None and src not in existing:
                rejected.append((p, f"abduced_from '{src}' is not a node")); continue
            # NEUTRAL attrs (default A()) — never the LLM's; status conjectural; on the frontier.
            self.g["nodes"].append(make_node(nid, kind, title, p.get("status", "conjectural"),
                                             statement=p.get("statement", ""), frontier=True))
            if src is not None:
                self.g["edges"].append(make_edge(nid, src, "abduced-from"))
            existing.add(nid); added.append(nid)
        self._index()
        return added, rejected

    # ---------------- DECISION ----------------
    def decision(self, d, weights=None):
        W = weights or self.cfg.weights
        rb_ready, rb_await, rb_else = self.cfg.ready_bonus
        pd = self.cfg.payoff_default

        def centrality(i):
            one = sum((self.N[t].get("attrs") or {}).get("payoff", pd) for t in self.out[i] if t in self.N)
            two = sum(0.5 * (self.N[t2].get("attrs") or {}).get("payoff", pd)
                      for t in self.out[i] if t in self.N
                      for t2 in self.out.get(t, []) if t2 in self.N)
            return min(1.0, (one + two) / 3.0)

        ranked = []
        for n in self.g["nodes"]:
            if not self.is_frontier(n):
                continue
            a = n.get("attrs") or {}; i = n["id"]; cen = centrality(i)
            rb = rb_ready if i in d["ready"] else (rb_await if i in d["awaiting"] else rb_else)
            score = (W["payoff"] * a.get("payoff", .5)
                     + W["centrality"] * cen
                     + W["tract"] * a.get("tractability", .5) * (1 - 0.5 * a.get("effort", .5))
                     + W["readiness"] * a.get("readiness", .5) * rb
                     + W["fit"] * a.get("strategic_fit", .5)
                     + W["info"] * a.get("info_value", .5)
                     - W["risk"] * a.get("risk", .3))
            ranked.append((round(score, 3), i, cen, rb, n))
        ranked.sort(reverse=True)
        return ranked

    def weight_sensitivity(self, delta=0.2):
        """Perturb each decision weight by ±delta (relative) and report frontier rank changes.

        Pure + deterministic. Answers "how fragile is the ranking to the hand-set weights?" — the
        audit behind F-FIT-WEAK-LEVER / T-DECISION-ECONOMY. `top_changed` (does the *recommended
        next action* flip?) is the decision-relevant signal; `fragile_nodes` are those that move
        rank under some single-weight ±delta. Scaling one weight can only re-order nodes that trade
        off *different* dimensions, so a stable top here is a genuine robustness statement.
        """
        d = self.deduction()
        base = [i for _, i, *_ in self.decision(d)]
        base_pos = {i: p for p, i in enumerate(base)}
        perturbations, fragile = [], set()
        for k in sorted(self.cfg.weights):
            for sign in (-1, 1):
                w = dict(self.cfg.weights)
                w[k] = round(w[k] * (1 + sign * delta), 6)
                order = [i for _, i, *_ in self.decision(d, w)]
                changed = [i for p, i in enumerate(order) if base_pos.get(i) != p]
                fragile.update(changed)
                perturbations.append(dict(weight=k, sign=("+" if sign > 0 else "-"),
                                          top=(order[0] if order else None),
                                          top_changed=(order[:1] != base[:1]),
                                          rank_changed=changed))
        return dict(delta=delta, baseline=base, baseline_top=(base[0] if base else None),
                    fragile_nodes=sorted(fragile), perturbations=perturbations)

    # ---------------- VALIDATE (pure linter) ----------------
    def validate(self):
        """Lint the graph for structural problems. Pure + deterministic — no LLM, no randomness.

        Returns a list of issues sorted for stable output; each is a dict
        ``{severity, code, where, msg}`` with severity ``"error"`` (the engine will misbehave) or
        ``"warning"`` (likely a typo / smell). Checks: duplicate ids, missing required fields,
        unknown kind/status/relation, attrs out of [0,1], dangling/self edges, prerequisite cycles.
        """
        from .schema import SCHEMA_VERSION
        cfg = self.cfg
        nodes = self.g.get("nodes", [])
        edges = self.g.get("edges", [])
        known_rel = cfg.prereq_rel | cfg.neg_rel | cfg.semantic_rel
        issues = []
        def add(sev, code, where, msg):
            issues.append(dict(severity=sev, code=code, where=where, msg=msg))

        # --- schema version ---
        sv = self.g.get("meta", {}).get("schema")
        if not sv:
            add("warning", "schema-missing", "meta", "no meta.schema — run `reasongraph migrate`")
        elif sv != SCHEMA_VERSION:
            add("warning", "schema-version", "meta",
                f"graph schema {sv!r} != engine {SCHEMA_VERSION!r} — run `reasongraph migrate`")

        # --- nodes ---
        seen = set()
        for k, n in enumerate(nodes):
            nid = n.get("id")
            where = nid or f"nodes[{k}]"
            if not nid:
                add("error", "missing-id", where, "node has no 'id'")
            elif nid in seen:
                add("error", "duplicate-id", nid, "duplicate node id")
            else:
                seen.add(nid)
            for field in ("kind", "title", "status"):
                if not n.get(field):
                    add("error", "missing-field", where, f"node missing '{field}'")
            kind, status = n.get("kind"), n.get("status")
            if kind and kind not in cfg.kinds:
                add("warning", "unknown-kind", where, f"kind '{kind}' not in the configured vocabulary")
            if status and status not in cfg.statuses:
                add("warning", "unknown-status", where,
                    f"status '{status}' not in the ladder — it will count as neither proven nor refuted")
            for ak, av in (n.get("attrs") or {}).items():
                if isinstance(av, (int, float)) and not (0.0 <= av <= 1.0):
                    add("warning", "attr-range", where, f"attr '{ak}'={av} is outside [0,1]")

        # --- edges ---
        for k, e in enumerate(edges):
            where = f"edges[{k}]"
            f, t, r = e.get("from"), e.get("to"), e.get("relation")
            if f not in seen:
                add("error", "dangling-edge", where, f"'from' references unknown node '{f}'")
            if t not in seen:
                add("error", "dangling-edge", where, f"'to' references unknown node '{t}'")
            if f is not None and f == t:
                add("warning", "self-edge", where, f"edge from '{f}' to itself")
            if not r:
                add("error", "missing-field", where, "edge missing 'relation'")
            elif r not in known_rel:
                add("warning", "unknown-relation", where,
                    f"relation '{r}' is in no group (prereq/negative/semantic) — treated as semantic")

        # --- prerequisite cycles (over valid prereq edges only) ---
        adj = {i: [] for i in seen}
        for e in edges:
            if e.get("relation") in cfg.prereq_rel and e.get("from") in seen and e.get("to") in seen:
                adj[e["from"]].append(e["to"])
        WHITE, GREY, BLACK = 0, 1, 2
        color = {i: WHITE for i in seen}
        reported = set()
        def visit(u, stack):
            color[u] = GREY
            stack.append(u)
            for v in adj[u]:
                if color[v] == GREY:
                    cyc = stack[stack.index(v):] + [v]
                    key = frozenset(cyc)
                    if key not in reported:
                        reported.add(key)
                        add("error", "prereq-cycle", " -> ".join(cyc), "circular prerequisite dependency")
                elif color[v] == WHITE:
                    visit(v, stack)
            stack.pop()
            color[u] = BLACK
        for i in sorted(seen):
            if color[i] == WHITE:
                visit(i, [])

        issues.sort(key=lambda x: (0 if x["severity"] == "error" else 1, x["code"], str(x["where"])))
        return issues

    def migrate(self):
        """Bring an older graph up to the current schema, idempotently and non-destructively.

        Additive only: stamps `meta.schema`, and backfills optional node keys that newer tooling
        expects (`attrs`, `evidence`) so external consumers don't trip on their absence. Never
        removes, renames, or reinterprets existing data — and never fabricates `frontier` intent.
        Returns a list of human-readable change strings ([] if the graph was already current). This
        is also the seam where any *future* breaking schema bump will live.
        """
        from .schema import SCHEMA_VERSION, A
        changes = []
        meta = self.g.setdefault("meta", {})
        if meta.get("schema") != SCHEMA_VERSION:
            changes.append(f"meta.schema {meta.get('schema')!r} -> {SCHEMA_VERSION!r}")
            meta["schema"] = SCHEMA_VERSION
        for n in self.g.get("nodes", []):
            if "attrs" not in n:
                n["attrs"] = A(); changes.append(f"{n.get('id', '?')}: backfilled default attrs")
            if "evidence" not in n:
                n["evidence"] = []; changes.append(f"{n.get('id', '?')}: backfilled empty evidence")
        self._index()
        return changes

    # ---------------- structured views (pure; for tooling) ----------------
    def pass_data(self):
        """The full pass as a JSON-serializable dict — same content as the text report, for tooling.

        Pure + deterministic. Sets become sorted lists; the ranked frontier carries the score,
        readiness tag, and centrality so downstream tools need not recompute them.
        """
        d = self.deduction()
        tag = {self.cfg.ready_bonus[0]: "ready", self.cfg.ready_bonus[1]: "awaiting"}
        ranked = [dict(node=i, score=sc, readiness=tag.get(rb, "blocked"), centrality=round(cen, 3),
                       title=n["title"]) for sc, i, cen, rb, n in self.decision(d)]
        return dict(
            thesis=self.g.get("meta", {}).get("thesis", ""),
            counts=dict(nodes=len(self.g["nodes"]), proven=len(d["proven"]),
                        refuted=len(d["refuted"]),
                        frontier=sum(1 for n in self.g["nodes"] if self.is_frontier(n))),
            deduction=dict(proven=sorted(d["proven"]), refuted=sorted(d["refuted"]),
                           ready=sorted(d["ready"]),
                           awaiting={k: d["awaiting"][k] for k in sorted(d["awaiting"])},
                           blocked={k: d["blocked"][k] for k in sorted(d["blocked"])}),
            decision=ranked,
            argument=self._argument_summary(),
            induction=[dict(kind=k, node=i, msg=m) for k, i, m in self.induction(d)],
            abduction=self.abduction(d),
        )

    def _argument_summary(self, gl=None):
        """Reinstated / structurally-defeated / undecided nodes from the grounded extension — only
        the nodes that participate in a `refutes` attack (so a graph with no attacks reports none)."""
        gl = gl or self.grounded_extension()
        R = self.cfg.refuted
        reinstated = sorted(i for i in self.N if gl[i] == "in" and self.att[i])  # defended, not just unattacked
        defeated = sorted(i for i in self.N if gl[i] == "out" and self.N[i]["status"] not in R)
        undecided = sorted(i for i in self.N if gl[i] == "undec" and (self.att[i] or
                           any(i in self.att[j] for j in self.N)))
        return dict(reinstated=reinstated, defeated=defeated, undecided=undecided)

    def node_view(self, nid):
        """A single node plus its graph context (prereqs/dependents/negatives + classification).

        Pure + deterministic. Raises KeyError for an unknown id. The decision score is included
        only when the node is on the frontier.
        """
        if nid not in self.N:
            raise KeyError(f"unknown node {nid}")
        n = self.N[nid]
        d = self.deduction()
        cls = ("ready" if nid in d["ready"] else "awaiting" if nid in d["awaiting"]
               else "blocked" if nid in d["blocked"]
               else "proven" if nid in d["proven"] else "refuted" if nid in d["refuted"] else "—")
        def ref(i):
            return dict(id=i, status=self.N[i]["status"], title=self.N[i]["title"]) if i in self.N else dict(id=i)
        score = next((sc for sc, i, *_ in self.decision(d) if i == nid), None)
        return dict(
            id=nid, kind=n["kind"], title=n["title"], statement=n.get("statement", ""),
            status=n["status"], classification=cls, confidence=n.get("confidence"),
            frontier=self.is_frontier(n), score=score, attrs=n.get("attrs", {}),
            blocked_by=self.blocking_causes(nid, d), opinion=self.opinion(n),
            evidence_profile=self.evidence_profile(n),
            grounded=self.grounded_extension().get(nid),
            evidence=n.get("evidence", []), notes=n.get("notes", []),
            prerequisites=[ref(p) for p in self.pre[nid]],
            negatives=[ref(p) for p in self.neg[nid]],
            feeds=[ref(t) for t in self.out[nid]],
        )

    # ---------------- VISUALIZE (pure exporters) ----------------
    def _classify(self):
        """Map each node id -> a status class for coloring: proven/refuted/ready/blocked/awaiting/open."""
        d = self.deduction()
        cls = {}
        for i in self.N:
            if i in d["proven"]:      cls[i] = "proven"
            elif i in d["refuted"]:   cls[i] = "refuted"
            elif i in d["ready"]:     cls[i] = "ready"
            elif i in d["blocked"]:   cls[i] = "blocked"
            elif i in d["awaiting"]:  cls[i] = "awaiting"
            else:                     cls[i] = "open"
        return cls

    def to_mermaid(self):
        """A Mermaid flowchart, status-colored. Pure + deterministic."""
        cls = self._classify()
        sid = {i: "n" + "".join(c if c.isalnum() else "_" for c in i) for i in self.N}
        style = dict(proven="fill:#c8e6c9,stroke:#2e7d32", refuted="fill:#ffcdd2,stroke:#c62828",
                     ready="fill:#bbdefb,stroke:#1565c0", blocked="fill:#ffe0b2,stroke:#e65100",
                     awaiting="fill:#f5f5f5,stroke:#9e9e9e", open="fill:#fff,stroke:#616161")
        L = ["flowchart TD"]
        for i, n in self.N.items():
            label = n["title"].replace('"', "'")
            L.append(f'  {sid[i]}["{i}: {label}"]:::{cls[i]}')
        for e in self.g["edges"]:
            f, t, r = e.get("from"), e.get("to"), e.get("relation")
            if f not in self.N or t not in self.N:
                continue
            if r in self.cfg.prereq_rel:
                L.append(f"  {sid[f]} --> {sid[t]}")
            elif r in self.cfg.neg_rel:
                L.append(f"  {sid[f]} -.->|{r}| {sid[t]}")
            else:
                L.append(f"  {sid[f]} -.->|{r}| {sid[t]}")
        for k, v in style.items():
            L.append(f"  classDef {k} {v};")
        return "\n".join(L)

    def to_dot(self):
        """A Graphviz DOT digraph, status-colored. Pure + deterministic."""
        cls = self._classify()
        fill = dict(proven="#c8e6c9", refuted="#ffcdd2", ready="#bbdefb",
                    blocked="#ffe0b2", awaiting="#f5f5f5", open="#ffffff")
        def q(s): return '"' + str(s).replace('"', '\\"') + '"'
        L = ["digraph reasongraph {", "  rankdir=TB;",
             '  node [shape=box, style="rounded,filled", fontname="Helvetica"];']
        for i, n in self.N.items():
            label = f"{i}: {n['title']}"
            L.append(f"  {q(i)} [label={q(label)}, fillcolor={q(fill[cls[i]])}];")
        for e in self.g["edges"]:
            f, t, r = e.get("from"), e.get("to"), e.get("relation")
            if f not in self.N or t not in self.N:
                continue
            if r in self.cfg.prereq_rel:
                L.append(f"  {q(f)} -> {q(t)} [label={q(r)}];")
            elif r in self.cfg.neg_rel:
                L.append(f"  {q(f)} -> {q(t)} [label={q(r)}, color=red, style=dashed];")
            else:
                L.append(f"  {q(f)} -> {q(t)} [label={q(r)}, color=gray, style=dotted];")
        L.append("}")
        return "\n".join(L)

    # ---------------- report + evolve ----------------
    def format_report(self):
        d = self.deduction()
        g = self.g
        L = [f"=== REASON-GRAPH — {g.get('meta', {}).get('thesis', '(no thesis)')} ===",
             f"nodes {len(g['nodes'])} | proven {len(d['proven'])} | refuted {len(d['refuted'])} "
             f"| frontier {sum(1 for n in g['nodes'] if self.is_frontier(n))}", "",
             "[DEDUCTION] ready (all prereqs proven): " + (", ".join(d["ready"]) or "none")]
        if d["blocked"]:
            L.append("           blocked by refutation: "
                     + "; ".join(f"{k}<-{self.blocking_causes(k, d)}" for k in d["blocked"]))
        arg = self._argument_summary()
        if arg["reinstated"] or arg["defeated"] or arg["undecided"]:
            parts = [f"{k} {', '.join(arg[k])}" for k in ("defeated", "reinstated", "undecided") if arg[k]]
            L.append("[ARGUMENT] grounded extension — " + "; ".join(parts))
        L += ["", "[DECISION] ranked frontier — what to tackle next:",
              f"  {'score':>6}  {'node':22} {'rdy':>5} {'cen':>4}  title"]
        for sc, i, cen, rb, n in self.decision(d):
            tag = "READY" if rb == self.cfg.ready_bonus[0] else ("near" if rb == self.cfg.ready_bonus[1] else "blkd")
            L.append(f"  {sc:>6}  {i:22} {tag:>5} {cen:>4.2f}  {n['title'][:70]}")
        L += ["", "[INDUCTION]"]
        for kind, i, msg in self.induction(d):
            L.append(f"  ({kind}) {i}: {msg}")
        L += ["", "[ABDUCTION] hypothesis tasks for an LLM pass:"]
        for t in self.abduction(d):
            L.append(f"  - [{t['trigger']}] {t['node']}: {t['prompt'][:120]}")
        return "\n".join(L)

    def report(self, log_path=None):
        s = self.format_report()
        print(s)
        if log_path:
            d = self.deduction()
            top = self.decision(d)[:3]
            with open(log_path, "a") as f:
                f.write("\n## pass\n- ready: " + (", ".join(d["ready"]) or "none")
                        + "\n- top-3: " + "; ".join(f"{i}({sc})" for sc, i, _, _, _ in top) + "\n")
        return s

    def add_finding(self, nid, status, confidence=None, note=None, evidence=None):
        if nid not in self.N:
            raise KeyError(f"unknown node {nid}; add it to your seed first")
        n = self.N[nid]
        n["status"] = status
        if confidence is not None:
            n["confidence"] = confidence
        if note:
            n.setdefault("notes", []).append(note)
        if evidence:
            n.setdefault("evidence", []).append(evidence)
        # NOTE: we deliberately do NOT mutate n["frontier"] here. Frontier membership is derived
        # each pass by is_frontier() from status, so a node drops off the frontier when it becomes
        # proven/refuted and returns to it if that finding is later overturned (recovery, not a
        # one-way stamp). See is_frontier() and docs/RESEARCH-NOTES.md §3.
        self._index()
        return n
