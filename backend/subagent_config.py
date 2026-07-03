"""Define typed subagent configuration models and parsing helpers."""

from dataclasses import dataclass
from typing import Any, Iterable, Literal

SubagentKind = Literal["genie", "serving_endpoint", "app"]
ALLOWED_SUBAGENT_KINDS = {"genie", "serving_endpoint", "app"}
SubagentAuthMode = Literal["app", "obo"]
ALLOWED_SUBAGENT_AUTH_MODES = {"app", "obo"}


@dataclass(frozen=True)
class SubagentConfig:
    """Canonical configuration model for a single orchestrated subagent."""
    name: str
    kind: SubagentKind
    description: str
    endpoint: str | None = None
    space_id: str | None = None
    auth_mode: SubagentAuthMode = "app"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Subagent name is required")
        if self.kind not in ALLOWED_SUBAGENT_KINDS:
            raise ValueError(
                f"Subagent {self.name!r} has unsupported type {self.kind!r}. "
                f"Allowed: {sorted(ALLOWED_SUBAGENT_KINDS)}"
            )
        if self.auth_mode not in ALLOWED_SUBAGENT_AUTH_MODES:
            raise ValueError(
                f"Subagent {self.name!r} has unsupported auth_mode {self.auth_mode!r}. "
                f"Allowed: {sorted(ALLOWED_SUBAGENT_AUTH_MODES)}"
            )
        if not self.description:
            raise ValueError(f"Subagent {self.name!r} must include a description")
        if self.kind == "genie" and not self.space_id:
            raise ValueError(f"Genie subagent {self.name!r} must define space_id")
        if self.kind != "genie" and not self.endpoint:
            raise ValueError(
                f"Non-genie subagent {self.name!r} must define endpoint"
            )

    @property
    def is_genie(self) -> bool:
        return self.kind == "genie"

    @property
    def is_obo(self) -> bool:
        return self.auth_mode == "obo"

    @property
    def tool_name(self) -> str:
        return f"query_{self.name}"

    @property
    def model_name(self) -> str:
        if self.endpoint is None:
            raise ValueError(f"Subagent {self.name!r} has no endpoint configured")
        return f"apps/{self.endpoint}" if self.kind == "app" else self.endpoint

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SubagentConfig":
        kind = value["type"]
        auth_mode = value.get("auth_mode", "obo" if kind == "genie" else "app")
        try:
            return cls(
                name=value["name"],
                kind=kind,
                description=value["description"],
                endpoint=value.get("endpoint"),
                space_id=value.get("space_id"),
                auth_mode=auth_mode,
            )
        except KeyError as exc:
            raise ValueError(f"Subagent config missing required key: {exc}") from exc


def parse_subagents(raw_subagents: Iterable[dict[str, Any]]) -> list[SubagentConfig]:
    """Parse and validate raw subagent dictionaries into typed models."""
    return [SubagentConfig.from_dict(value) for value in raw_subagents]


RAW_SUBAGENTS: list[dict[str, Any]] = [
    {
        "name": "sales_agent",
        "type": "genie",
        "auth_mode": "obo",
        "space_id": "01f159f5d91419549020e3609add391c",
        "description": (
            "Sales agent backed by a Genie space for structured data analysis. "
            "Use this for sales metrics, store performance, and operational reporting."
        ),
    },
    {
        "name": "knowledge_assistant",
        "type": "serving_endpoint",
        "auth_mode": "app",
        "endpoint": "knowledge_assistant",
        "description": (
            "Query the knowledge-assistant endpoint on Model Serving. "
            "Use this for documentation and policy lookups. "
            "The endpoint must have task type agent/v1/responses."
        ),
    },
    {
        "name": "lakebase_vector",
        "type": "serving_endpoint",
        "auth_mode": "app",
        "endpoint": "lakebase_vector_storage",
        "description": (
            "Query the Lakebase-backed vector storage endpoint on Model Serving. "
            "Use this for semantic retrieval and vector-search style lookups. "
            "The endpoint must have task type agent/v1/responses."
        ),
    },
]


SUBAGENTS = parse_subagents(RAW_SUBAGENTS)
