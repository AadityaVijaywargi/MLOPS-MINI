"""Self-verification (A3). Runs on the assessor's raw output before anything is
returned. A finding survives only if:

  citation_resolves  its provision_id is a passage this run actually retrieved
  quote_in_passage   its quote is (normalised) verbatim text of that passage
  numbers_traceable  every number it relies on appears in the passage or the
                     proposal (or follows from them by the stated derivation)
  status_consistent  satisfied/violated agrees with proposed <cmp> required

The same checks yield the quality metrics used offline (eval) and online."""
from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field
from typing import Any

_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.UAdd: operator.pos}
_CMP = {"<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt, "==": lambda a, b: abs(a - b) < 1e-6}
STATUSES = {"satisfied", "violated", "not_determinable", "not_applicable"}


def normalise(text: str) -> str:
    t = (text or "").lower()
    t = t.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}))
    return re.sub(r"[^a-z0-9.%]+", "", t)


def numbers(text: str) -> list[float]:
    return [float(x) for x in _NUM.findall((text or "").replace(",", ""))]


def flatten_numbers(obj: Any) -> list[float]:
    out: list[float] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(flatten_numbers(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(flatten_numbers(v))
    return out


def safe_eval(expr: str) -> float:
    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("min", "max"):
            return {"min": min, "max": max}[node.func.id](*(ev(a) for a in node.args))
        raise ValueError("unsupported expression")
    cleaned = re.sub(r"(?<=[\d)])\s*[x×X]\s*(?=[\d(])", " * ", expr)
    cleaned = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", cleaned)
    return ev(ast.parse(cleaned.split("=")[0].strip(), mode="eval"))


def _close(a: float, b: float, rel: float = 0.01) -> bool:
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), 1e-6)


def _member(x: float, pool: list[float]) -> bool:
    return any(_close(x, y) for y in pool)


@dataclass
class FindingCheck:
    index: int
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class VerificationReport:
    checks: list[FindingCheck]
    coverage_missing: list[str]
    total_findings: int
    total_citations: int
    grounded_citations: int
    numeric_findings: int
    consistent_numeric_findings: int
    hallucinated_findings: int

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks) and not self.coverage_missing and self.total_findings > 0

    @property
    def groundedness(self) -> float | None:
        return self.grounded_citations / self.total_citations if self.total_citations else None

    @property
    def faithfulness(self) -> float | None:
        return self.consistent_numeric_findings / self.numeric_findings if self.numeric_findings else None

    @property
    def hallucination_rate(self) -> float | None:
        return self.hallucinated_findings / self.total_findings if self.total_findings else None

    def errors(self) -> list[str]:
        out = [f"finding[{c.index}]: {e}" for c in self.checks for e in c.errors]
        out += [f"missing mandatory topic: {t}" for t in self.coverage_missing]
        return out

    def to_dict(self) -> dict:
        return {"passed": self.passed, "errors": self.errors(), "groundedness": self.groundedness,
                "faithfulness": self.faithfulness, "hallucination_rate": self.hallucination_rate,
                "total_findings": self.total_findings, "total_citations": self.total_citations}


def verify_findings(findings: list[dict], passages: dict[str, dict], proposal: dict,
                    mandatory_topics: tuple[str, ...]) -> VerificationReport:
    proposal_nums = flatten_numbers(proposal)
    checks: list[FindingCheck] = []
    grounded = citations = numeric = consistent = hallucinated = 0
    covered: set[str] = set()
    for i, f in enumerate(findings):
        chk = FindingCheck(i)
        status = f.get("status")
        if status not in STATUSES:
            chk.errors.append(f"invalid status {status!r}")
        pid = f.get("provision_id")
        passage = passages.get(pid or "")
        quote = f.get("quote") or ""
        untraceable = False
        citations += 1
        if passage is None:
            chk.errors.append(f"citation_unresolved: {pid!r} was not retrieved in this run")
            untraceable = True
        else:
            if len(normalise(quote)) < 6 or normalise(quote) not in normalise(passage["text"]):
                chk.errors.append("quote_not_in_passage: quote is not verbatim text of the cited provision")
                untraceable = True
            else:
                grounded += 1
        allowed = proposal_nums + [0.0, 1.0, 100.0]
        if passage is not None:
            pn = numbers(passage["text"]) + numbers(passage.get("header", ""))
            allowed += pn + [n / 100 for n in pn]
        req, prop = f.get("required_value"), f.get("proposed_value")
        deriv = f.get("derivation")
        if isinstance(req, (int, float)) and not isinstance(req, bool):
            if deriv:
                if any(not _member(n, allowed) for n in numbers(deriv.split("=")[0])):
                    chk.errors.append(f"number_untraceable: derivation '{deriv}' uses numbers not in passage/proposal")
                    untraceable = True
                else:
                    try:
                        if not _close(safe_eval(deriv), float(req), 0.02):
                            chk.errors.append(f"derivation_mismatch: '{deriv}' != {req}")
                    except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
                        chk.errors.append(f"derivation_unparseable: '{deriv}'")
            elif not _member(float(req), allowed):
                chk.errors.append(f"number_untraceable: required_value {req} not in passage or proposal")
                untraceable = True
        if isinstance(prop, (int, float)) and not isinstance(prop, bool) and not _member(float(prop), allowed):
            chk.errors.append(f"number_untraceable: proposed_value {prop} not in proposal")
            untraceable = True
        cmp = f.get("comparison")
        if (status in ("satisfied", "violated") and cmp in _CMP and isinstance(req, (int, float))
                and isinstance(prop, (int, float))):
            numeric += 1
            holds = _CMP[cmp](float(prop), float(req))
            if (status == "satisfied") == holds:
                consistent += 1
            else:
                chk.errors.append(f"status_inconsistent: {prop} {cmp} {req} is {holds} but status is {status}")
        if untraceable:
            hallucinated += 1
        if chk.ok and status in ("satisfied", "violated", "not_applicable"):
            covered.add(f.get("topic", ""))
        checks.append(chk)
    missing = [t for t in mandatory_topics if t not in covered]
    return VerificationReport(checks, missing, len(findings), citations, grounded, numeric, consistent, hallucinated)
