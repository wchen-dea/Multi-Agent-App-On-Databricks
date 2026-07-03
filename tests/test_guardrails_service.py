from backend.domain.subagent_config import SubagentConfig
from backend.services.guardrails_service import evaluate_response_guardrails


def _governed_subagents() -> list[SubagentConfig]:
    return [
        SubagentConfig(
            name="governed_docs",
            kind="serving_endpoint",
            auth_mode="app",
            endpoint="docs",
            data_classification="restricted",
            requires_evidence=True,
            description="governed",
        )
    ]


def test_guardrails_blocks_missing_evidence_for_governed_answers():
    result = evaluate_response_guardrails("Here is the answer without source.", _governed_subagents())

    assert result.blocked is True
    assert "evidence_required" in result.reasons


def test_guardrails_blocks_low_confidence_sensitive_output():
    result = evaluate_response_guardrails(
        "I think the confidential total might be around 100.",
        _governed_subagents(),
    )

    assert result.blocked is True
    assert "low_confidence_sensitive" in result.reasons


def test_guardrails_allows_governed_output_with_citation_and_confident_text():
    result = evaluate_response_guardrails(
        "Revenue is 100 [1] Source: governed warehouse extract.",
        _governed_subagents(),
    )

    assert result.blocked is False
    assert result.reasons == ()
