"""Guardrails (L4).

Input side:  prompt-injection screening and toxicity detection on every free-text
             field before it can reach a model; flagged notes are withheld from
             the agents entirely (they never see the text) and the run is routed
             to specialist review.
Structural:  any free text that is passed on is wrapped as inert, escaped data.
Output side: the system may only *report findings*; sentences that would issue
             a determination it is not authorised to make (approval,
             certification, sanction) are rewritten, and the route is chosen by
             deterministic code, never by the model."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_INJECTION_PATTERNS: list[tuple[str, float]] = [
    (r"\b(ignore|disregard|forget|override)\b[^.]{0,40}\b(previous|prior|above|earlier|all|system|your)\b[^.]{0,20}"
     r"\b(instruction|instructions|prompt|prompts|rules|guidelines)\b", 0.9),
    (r"\byou are (now|no longer)\b", 0.6),
    (r"\b(system|developer)\s*(prompt|message|instructions?)\b", 0.6),
    (r"\b(act|behave|respond) as\b", 0.4),
    (r"\b(mark|route|classify|declare|treat|report|set)\b[^.]{0,30}\b(as|to)\b[^.]{0,10}"
     r"\b(clear[- ]for[- ]submission|compliant|approved|satisf(y|ied))\b", 0.9),
    (r"\b(do not|don't|never)\s+(escalate|flag|cite|verify|check)\b", 0.8),
    (r"\b(new|updated|additional) instructions?\b", 0.6),
    (r"</?\s*(system|assistant|user|tool|instructions?)\s*>", 0.8),
    (r"\b(tool_calls?|function_call|record_provision|finish_research|search_corpus)\b", 0.7),
    (r"\bjailbreak|\bDAN\b|developer mode", 0.8),
    (r"\b(reveal|print|show|repeat)\b[^.]{0,20}\b(prompt|instructions|secrets?|api key)\b", 0.8),
    (r"\bpretend\b", 0.4),
]

# A small lexicon-based detector: deliberately conservative (no false positives on
# bye-law vocabulary such as "kill switch" or "dead load" are expected because we
# match abusive phrases, not single technical words).
_TOXIC_PATTERNS = [
    r"\b(fuck\w*|shit\w*|bastard\w*|bitch\w*|asshole\w*|moron\w*|idiot\w*|stupid (officer|engineer|clerk|people))\b",
    r"\b(i('ll| will)|we('ll| will)) (kill|hurt|beat|destroy) (you|him|her|them)\b",
    r"\b(go to hell|shut up|scum|retard\w*)\b",
    r"\bhate (you|them|these people)\b",
]

_FORBIDDEN_DETERMINATIONS = [
    r"\b(the )?(plan|proposal|building|project|design)\b[^.]{0,40}\b(is|are|has been|stands|was)\b\s*"
    r"(hereby\s+)?(fully\s+|entirely\s+)?(approved|certified|sanctioned|compliant|legal)\b",
    r"\b(hereby\s+)?(certif(y|ies|ied)|approve[sd]?|sanction(s|ed)?)\b[^.]{0,30}\b(plan|proposal|building|construction)\b",
    r"\bapproved for (construction|submission|sanction)\b",
    r"\b(guarantee[sd]?|assure[sd]?)\b[^.]{0,30}\b(approval|sanction|compliance)\b",
    r"\bno (further )?(professional |human )?(review|check) (is )?(needed|required|necessary)\b",
    r"\b(fully|100%) compliant\b",
]

INJECTION_THRESHOLD = 0.8


@dataclass
class ScreenResult:
    injection_score: float = 0.0
    injection_matches: list[str] = field(default_factory=list)
    toxic: bool = False
    toxic_matches: list[str] = field(default_factory=list)

    @property
    def injection(self) -> bool:
        return self.injection_score >= INJECTION_THRESHOLD

    def flags(self) -> list[str]:
        out = []
        if self.injection:
            out.append("prompt_injection_suspected")
        if self.toxic:
            out.append("toxic_content")
        return out


def screen_text(text: str) -> ScreenResult:
    res = ScreenResult()
    if not text:
        return res
    lowered = text.lower()
    score = 0.0
    for pattern, weight in _INJECTION_PATTERNS:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if m:
            res.injection_matches.append(m.group(0)[:80])
            score = 1 - (1 - score) * (1 - weight)  # noisy-or
    res.injection_score = round(score, 3)
    for pattern in _TOXIC_PATTERNS:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if m:
            res.toxic = True
            res.toxic_matches.append(m.group(0)[:40])
    return res


def wrap_untrusted(text: str) -> str:
    """Spotlighting: escape and fence untrusted text so it reads as data."""
    escaped = html.escape(text or "", quote=False)
    return f"<untrusted_user_notes>\n{escaped}\n</untrusted_user_notes>"


def filter_output_text(text: str) -> tuple[str, list[str]]:
    """Rewrite sentences that would issue an unauthorised determination."""
    if not text:
        return text, []
    violations: list[str] = []
    out = text
    for pattern in _FORBIDDEN_DETERMINATIONS:
        for m in list(re.finditer(pattern, out, flags=re.IGNORECASE)):
            violations.append(m.group(0)[:80])
        out = re.sub(
            pattern,
            "[determination withheld: only a licensed professional can make this determination]",
            out,
            flags=re.IGNORECASE,
        )
    tox = screen_text(out)
    if tox.toxic:
        violations.extend(f"toxic:{t}" for t in tox.toxic_matches)
        for pattern in _TOXIC_PATTERNS:
            out = re.sub(pattern, "[removed]", out, flags=re.IGNORECASE)
    return out, violations
