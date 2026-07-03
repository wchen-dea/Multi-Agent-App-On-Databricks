"""Response guardrails for governed/sensitive outputs."""

from dataclasses import dataclass
import re

from backend.domain.subagent_config import SubagentConfig


@dataclass(frozen=True)
class GuardrailResult:
    """Guardrail decision for a model response."""

    blocked: bool
    reasons: tuple[str, ...]


_LOW_CONFIDENCE_PATTERNS = [
    r"\bnot sure\b",
    r"\buncertain\b",
    r"\bi think\b",
    r"\bmaybe\b",
    r"\bcould be\b",
    r"\bmight be\b",
]

_UNSAFE_PATTERNS = [
    r"\bssn\b",
    r"\bsocial security number\b",
    r"\bcredit card number\b",
    r"\bprivate key\b",
    r"\bapi key\b",
    r"\bpassword\b",
]


def _has_citation(text: str) -> bool:
    return bool(
        re.search(r"\[[0-9]+\]", text)
        or re.search(r"\bsource:\b", text, flags=re.IGNORECASE)
        or re.search(r"\bcitation:\b", text, flags=re.IGNORECASE)
    )


def evaluate_response_guardrails(
    response_text: str,
    governed_subagents: list[SubagentConfig],
) -> GuardrailResult:
    """Apply deterministic guardrails to block risky governed responses."""
    text = response_text.strip()
    lowered = text.lower()
    reasons: list[str] = []

    requires_evidence = any(s.requires_evidence for s in governed_subagents)
    has_sensitive_data = any(
        s.data_classification in {"confidential", "restricted"} for s in governed_subagents
    )

    if requires_evidence and text and not _has_citation(text):
        reasons.append("evidence_required")

    if any(re.search(pattern, lowered) for pattern in _UNSAFE_PATTERNS):
        reasons.append("unsafe_output")

    if has_sensitive_data and any(re.search(pattern, lowered) for pattern in _LOW_CONFIDENCE_PATTERNS):
        reasons.append("low_confidence_sensitive")

    return GuardrailResult(blocked=bool(reasons), reasons=tuple(sorted(set(reasons))))
