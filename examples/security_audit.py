"""Second worked example — a different domain, to prove portability.

This models an *authorized security audit* as a reason-graph and runs one pass. The point: the
engine, the four modes, the decision formula, and the loop are **unchanged** — only `GraphConfig`
(the status ladder, the `kind` vocabulary, the weights) and the graph content differ. If reasongraph
can steer a security engagement with zero engine edits, the "domain-invariant" claim is earned, not
asserted.

Domain mapping:
  * a vulnerability is *confirmed* (an established fact → like `proven`) or dismissed as a
    *false-positive* / *risk-accepted* (→ like `refuted`, which blocks the remediations that hung
    off it);
  * a *control* that is *deployed* is an established building block;
  * a *remediation* is an open target ranked by risk-reduction (payoff), effort, and blast-radius
    (risk); a *probe* is an open data-gathering experiment.

    python examples/security_audit.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reasongraph import A, make_node, make_edge, new_graph, save, ReasonGraph, GraphConfig  # noqa: E402

# --- the ONLY porting surface: a domain-tuned config (engine untouched) ---
SEC = GraphConfig(
    proven=frozenset({"confirmed", "deployed"}),        # an established prerequisite
    refuted=frozenset({"false-positive", "risk-accepted"}),  # dismissed → blocks dependents + abduces
    kinds=frozenset({"asset", "vuln", "control", "remediation", "probe", "hypothesis", "reframe"}),
    statuses=frozenset({"open", "triaging", "confirmed", "deployed", "mitigated",
                        "false-positive", "risk-accepted"}),
    # risk-reduction matters most; blast-radius (risk) is a real but smaller deduction here.
    weights=dict(payoff=.30, centrality=.18, tract=.14, readiness=.12, fit=.12, info=.08, risk=.06),
)

def build():
  """Build the security-audit graph. Kept in a function so `SEC` can be imported side-effect-free
  (e.g. by `reasongraph --config examples/security_audit.py:SEC`)."""
  g = new_graph(thesis="authorized security audit — reduce real risk to the crown-jewel data",
                engagement="ACME Corp external + authenticated app test (scoped, authorized)")
  N, E = g["nodes"], g["edges"]
  def node(*a, **k): N.append(make_node(*a, **k))
  def edge(*a, **k): E.append(make_edge(*a, **k))
  # custom kinds aren't auto-frontier (make_node only auto-flags target/experiment), so open
  # remediations/probes set frontier explicitly — graph authoring, not an engine change.
  def rem(id, title, **attrs): node(id, "remediation", title, "open", attrs=A(**attrs), frontier=True)

  # --- deployed controls (established building blocks) ---
  node("C-WAF", "control", "Edge WAF deployed", "deployed", attrs=A(payoff=.4))
  node("C-MFA", "control", "MFA enforced on admin accounts", "deployed", attrs=A(payoff=.4))
  node("C-LOG", "control", "Centralized audit logging", "deployed", attrs=A(payoff=.3))

  # --- findings (+/- both first-class) ---
  node("V-SQLI", "vuln", "SQL injection in legacy reporting endpoint", "confirmed", attrs=A(payoff=.9))
  node("V-IDOR", "vuln", "IDOR on invoice download", "confirmed", attrs=A(payoff=.8))
  node("V-XSS", "vuln", "Reflected XSS in search", "triaging", attrs=A(payoff=.6))   # not yet confirmed
  node("V-RCE", "vuln", "Unauth RCE in EOL legacy appliance", "confirmed", attrs=A(payoff=.95))
  node("V-REDIRECT", "vuln", "Open redirect on login", "false-positive", attrs=A(info=.3),
       statement="Flagged by the scanner; manual review shows the target is allow-listed — not exploitable.")
  node("F-VENDOR-EOL", "vuln", "Vendor patch for the appliance is unavailable (end-of-life)",
       "risk-accepted", attrs=A(info=.6),
       statement="The obvious fix (apply the vendor patch) is dead — the appliance is EOL, no patch exists.")

  # --- remediations (open targets) ---
  rem("R-SQLI", "Parameterize the reporting queries", payoff=.9, effort=.25, ready=.9, fit=.9, risk=.15)
  rem("R-IDOR", "Add object-level authorization to invoice download", payoff=.8, effort=.35, ready=.85, fit=.85, risk=.2)
  rem("R-XSS", "Output-encode search results", payoff=.6, effort=.3, ready=.6, fit=.7, risk=.15)
  rem("R-REDIRECT", "Allow-list redirect targets", payoff=.3, effort=.2, fit=.4, risk=.1)  # moot if false-positive
  rem("R-RCE-PATCH", "Apply the vendor patch to the legacy appliance", payoff=.95, effort=.3, fit=.95, risk=.3)
  rem("R-WAF-VPATCH", "Virtual-patch the SQLi at the WAF (compensating control)", payoff=.6, effort=.2, ready=.9, fit=.7, risk=.2)
  node("P-PHISH", "probe", "Phishing simulation to size human risk", "open",
       attrs=A(payoff=.5, info=.85, effort=.4), frontier=True)

  # --- prerequisite edges (a confirmed vuln/deployed control enables its remediation) ---
  edge("V-SQLI", "R-SQLI", "enables")
  edge("V-IDOR", "R-IDOR", "enables")
  edge("C-MFA", "R-IDOR", "enables")          # object authz builds on enforced identity
  edge("V-XSS", "R-XSS", "enables")           # V-XSS is only triaging -> R-XSS AWAITS confirmation
  edge("V-REDIRECT", "R-REDIRECT", "enables") # false-positive prereq -> R-REDIRECT BLOCKED (moot)
  edge("V-RCE", "R-RCE-PATCH", "enables")     # the vuln is real...
  edge("F-VENDOR-EOL", "R-RCE-PATCH", "enables")  # ...but the patch route is risk-accepted -> BLOCKED
  edge("C-WAF", "R-WAF-VPATCH", "enables")
  edge("C-LOG", "P-PHISH", "enables")         # need logging to measure the simulation
  # --- negative edge: the compensating control is an alternative to the real fix ---
  edge("R-WAF-VPATCH", "R-SQLI", "tensions-with")
  return g


if __name__ == "__main__":
    g = build()
    out = os.path.join(os.path.dirname(__file__), "security_audit.json")
    save(g, out)
    print(f"wrote {out}\n")
    ReasonGraph(g, SEC).report()
