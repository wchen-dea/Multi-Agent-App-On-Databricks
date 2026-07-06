"""Provide policy enforcement helpers for governed subagent access."""

from dataclasses import dataclass
from typing import Literal

from mlflow.types.responses import ResponsesAgentRequest

from backend.domain.subagent_config import SubagentConfig
from backend.shared.settings import get_settings
from backend.shared.runtime_utils import RequestIdentityContext


@dataclass(frozen=True)
class PolicyContext:
    """Request-scoped inputs consumed by governed policy checks.

    Attributes:
        persona: Normalized persona from request inputs or default settings.
        has_user_identity: Whether forwarded user identity is available.
        requested_tool: Explicit tool hint from request inputs, if provided.
        request_confidence: Optional confidence score attached to the request.
    """

    persona: str | None
    has_user_identity: bool
    requested_tool: str | None
    request_confidence: float | None


@dataclass(frozen=True)
class PolicyDecision:
    """Represent a per-subagent policy allow/deny decision.

    Attributes:
        subagent_name: Subagent configuration name.
        tool_name: Tool name exposed to orchestrator routing.
        allowed: True when subagent is policy-eligible for this request.
        reason_code: Machine-readable decision category.
        reason: Human-readable explanation for auditing and diagnostics.
    """

    subagent_name: str
    tool_name: str
    allowed: bool
    reason_code: Literal[
        "allowed",
        "tool_not_requested",
        "persona_required",
        "persona_not_allowed",
        "obo_identity_required",
        "low_confidence_sensitive",
    ]
    reason: str


def build_policy_context(
    request: ResponsesAgentRequest,
    identity_ctx: RequestIdentityContext,
) -> PolicyContext:
    """Build policy context from request custom inputs and identity state.

    Args:
        request: Incoming Responses API request that may carry custom inputs.
        identity_ctx: Request identity context used for OBO-aware policy rules.

    Returns:
        Normalized policy context used by subagent filtering.

    Notes:
        Persona defaults to configured runtime settings when not provided by
        request custom inputs.
    """
    persona: str | None = None
    default_persona = get_settings().default_request_persona.strip().lower() or None
    requested_tool: str | None = None
    request_confidence: float | None = None
    custom_inputs = request.custom_inputs
    if isinstance(custom_inputs, dict):
        raw = custom_inputs.get("persona")
        if isinstance(raw, str) and raw.strip():
            persona = raw.strip().lower()
        raw_tool = custom_inputs.get("tool")
        if isinstance(raw_tool, str) and raw_tool.strip():
            requested_tool = raw_tool.strip()
        raw_confidence = custom_inputs.get("confidence")
        if isinstance(raw_confidence, (int, float)):
            request_confidence = float(raw_confidence)

    if persona is None:
        persona = default_persona

    return PolicyContext(
        persona=persona,
        has_user_identity=identity_ctx.has_user_identity,
        requested_tool=requested_tool,
        request_confidence=request_confidence,
    )


def filter_subagents_by_policy(
    subagents: list[SubagentConfig],
    context: PolicyContext,
) -> tuple[list[SubagentConfig], list[PolicyDecision]]:
    """Filter subagents by policy and return full decision trace.

    Args:
        subagents: Candidate subagents to evaluate.
        context: Request policy context.

    Returns:
        A tuple of:
        - Subagents allowed for routing.
        - Per-subagent allow/deny decisions for observability.

    Notes:
        Sensitive classifications require minimum confidence regardless of
        auth mode.
    """
    allowed: list[SubagentConfig] = []
    decisions: list[PolicyDecision] = []
    sensitive_threshold = 0.75

    for subagent in subagents:
        if context.requested_tool and context.requested_tool not in {
            subagent.name,
            subagent.tool_name,
        }:
            decisions.append(
                PolicyDecision(
                    subagent_name=subagent.name,
                    tool_name=subagent.tool_name,
                    allowed=False,
                    reason_code="tool_not_requested",
                    reason=(
                        f"{subagent.name} policy deny (requested tool "
                        f"{context.requested_tool!r} does not match)"
                    ),
                )
            )
            continue

        if subagent.allowed_personas:
            if context.persona is None:
                decisions.append(
                    PolicyDecision(
                        subagent_name=subagent.name,
                        tool_name=subagent.tool_name,
                        allowed=False,
                        reason_code="persona_required",
                        reason=f"{subagent.name} policy deny (persona is required)",
                    )
                )
                continue
            if context.persona not in {p.lower() for p in subagent.allowed_personas}:
                decisions.append(
                    PolicyDecision(
                        subagent_name=subagent.name,
                        tool_name=subagent.tool_name,
                        allowed=False,
                        reason_code="persona_not_allowed",
                        reason=(
                            f"{subagent.name} policy deny (persona {context.persona!r} "
                            "is not allowed)"
                        ),
                    )
                )
                continue

        if subagent.auth_mode == "obo" and not context.has_user_identity:
            decisions.append(
                PolicyDecision(
                    subagent_name=subagent.name,
                    tool_name=subagent.tool_name,
                    allowed=False,
                    reason_code="obo_identity_required",
                    reason=(
                        f"{subagent.name} policy deny (OBO identity is required for "
                        "auth_mode=obo)"
                    ),
                )
            )
            continue

        if (
            subagent.data_classification in {"confidential", "restricted"}
            and context.request_confidence is not None
            and context.request_confidence < sensitive_threshold
        ):
            if not context.has_user_identity:
                # Already denied by auth-mode check above for OBO. Keep rule explicit for app tools too.
                pass
            decisions.append(
                PolicyDecision(
                    subagent_name=subagent.name,
                    tool_name=subagent.tool_name,
                    allowed=False,
                    reason_code="low_confidence_sensitive",
                    reason=(
                        f"{subagent.name} policy deny (confidence "
                        f"{context.request_confidence:.2f} is below threshold {sensitive_threshold:.2f} "
                        f"for {subagent.data_classification} data)"
                    ),
                )
            )
            continue

        allowed.append(subagent)
        decisions.append(
            PolicyDecision(
                subagent_name=subagent.name,
                tool_name=subagent.tool_name,
                allowed=True,
                reason_code="allowed",
                reason=(
                    f"{subagent.name} policy allow (auth_mode={subagent.auth_mode}, "
                    f"classification={subagent.data_classification})"
                )
            )
        )

    return allowed, decisions
