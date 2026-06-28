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
from .schema import GraphConfig


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
        for e in self.g["edges"]:
            f, t, r = e["from"], e["to"], e["relation"]
            if f not in N or t not in N:
                continue
            if r in self.cfg.prereq_rel:
                pre[t].append(f); out[f].append(t)
            elif r in self.cfg.neg_rel:
                neg[t].append(f); out[f].append(t)
            else:
                out[f].append(t)
        self.N, self.pre, self.out, self.neg = N, pre, out, neg

    # ---------------- DEDUCTION ----------------
    def deduction(self):
        P, R = self.cfg.proven, self.cfg.refuted
        proven = {i for i, n in self.N.items() if n["status"] in P}
        refuted = {i for i, n in self.N.items() if n["status"] in R}
        ready, blocked, awaiting = {}, {}, {}
        for i, n in self.N.items():
            if n["status"] != "open":
                continue
            ps = self.pre[i]
            ref_ps = [p for p in ps if self.N[p]["status"] in R]
            open_ps = [p for p in ps if self.N[p]["status"] not in P | R]
            if ref_ps:
                blocked[i] = ref_ps
            elif not open_ps:
                ready[i] = True
            else:
                awaiting[i] = open_ps
        return dict(proven=proven, refuted=refuted, ready=ready, blocked=blocked, awaiting=awaiting)

    # ---------------- INDUCTION ----------------
    def induction(self, d):
        out = []
        for n in self.g["nodes"]:
            ev = n.get("evidence", [])
            if n["status"] in self.cfg.proven and n["kind"] == "finding":
                indep = any(any(h in str(e).lower() for h in self.cfg.independent_hints) for e in ev)
                if len(ev) >= self.cfg.generalize_support_min or indep:
                    out.append(("generalize?", n["id"],
                                "multi/independent support — propose a generalized claim node"))
            if n["status"] in self.cfg.thin:
                out.append(("strengthen", n["id"],
                            "thin evidence — confidence capped until an enabling experiment lands"))
        return out

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
            if self.N[i]["attrs"].get("payoff", 0) >= self.cfg.blocked_payoff_min:
                tasks.append(dict(trigger="blocked-goal", node=i,
                    prompt=(f"BLOCKED high-value target: {self.N[i]['title']} (blocked by refuted "
                            f"{miss}). Abduce a repair path / alternative lemma routing around the "
                            "refuted prerequisite.")))
        for n in self.g["nodes"]:
            if n.get("frontier") and n["attrs"].get("info_value", 0) >= self.cfg.high_info_min:
                tasks.append(dict(trigger="high-info", node=n["id"],
                    prompt=(f"HIGH-INFORMATION target {n['id']}: enumerate the 2-3 outcomes "
                            "(positive AND negative) and what each entails downstream, so the "
                            "result is decision-useful either way.")))
        return tasks

    # ---------------- DECISION ----------------
    def decision(self, d):
        W = self.cfg.weights
        rb_ready, rb_await, rb_else = self.cfg.ready_bonus
        pd = self.cfg.payoff_default

        def centrality(i):
            one = sum(self.N[t]["attrs"].get("payoff", pd) for t in self.out[i] if t in self.N)
            two = sum(0.5 * self.N[t2]["attrs"].get("payoff", pd)
                      for t in self.out[i] if t in self.N
                      for t2 in self.out.get(t, []) if t2 in self.N)
            return min(1.0, (one + two) / 3.0)

        ranked = []
        for n in self.g["nodes"]:
            if not n.get("frontier"):
                continue
            a = n["attrs"]; i = n["id"]; cen = centrality(i)
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

    # ---------------- VALIDATE (pure linter) ----------------
    def validate(self):
        """Lint the graph for structural problems. Pure + deterministic — no LLM, no randomness.

        Returns a list of issues sorted for stable output; each is a dict
        ``{severity, code, where, msg}`` with severity ``"error"`` (the engine will misbehave) or
        ``"warning"`` (likely a typo / smell). Checks: duplicate ids, missing required fields,
        unknown kind/status/relation, attrs out of [0,1], dangling/self edges, prerequisite cycles.
        """
        cfg = self.cfg
        nodes = self.g.get("nodes", [])
        edges = self.g.get("edges", [])
        known_rel = cfg.prereq_rel | cfg.neg_rel | cfg.semantic_rel
        issues = []
        def add(sev, code, where, msg):
            issues.append(dict(severity=sev, code=code, where=where, msg=msg))

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
                        frontier=sum(1 for n in self.g["nodes"] if n.get("frontier"))),
            deduction=dict(proven=sorted(d["proven"]), refuted=sorted(d["refuted"]),
                           ready=sorted(d["ready"]),
                           awaiting={k: d["awaiting"][k] for k in sorted(d["awaiting"])},
                           blocked={k: d["blocked"][k] for k in sorted(d["blocked"])}),
            decision=ranked,
            induction=[dict(kind=k, node=i, msg=m) for k, i, m in self.induction(d)],
            abduction=self.abduction(d),
        )

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
            frontier=bool(n.get("frontier")), score=score, attrs=n.get("attrs", {}),
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
             f"| frontier {sum(1 for n in g['nodes'] if n.get('frontier'))}", "",
             "[DEDUCTION] ready (all prereqs proven): " + (", ".join(d["ready"]) or "none")]
        if d["blocked"]:
            L.append("           blocked by refutation: "
                     + "; ".join(f"{k}<-{v}" for k, v in d["blocked"].items()))
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
        if status in self.cfg.proven | self.cfg.refuted:
            n["frontier"] = False
        self._index()
        return n
