"""Define typed subagent configuration models and parsing helpers."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

SubagentKind = Literal["genie", "serving_endpoint", "app"]
ALLOWED_SUBAGENT_KINDS = {"genie", "serving_endpoint", "app"}
SubagentAuthMode = Literal["app", "obo"]
ALLOWED_SUBAGENT_AUTH_MODES = {"app", "obo"}
DataClassification = Literal["public", "internal", "confidential", "restricted"]
ALLOWED_DATA_CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}


@dataclass(frozen=True)
class SubagentConfig:
    """Canonical configuration model for a single orchestrated subagent."""

    name: str
    kind: SubagentKind
    description: str
    endpoint: str | None = None
    space_id: str | None = None
    auth_mode: SubagentAuthMode = "app"
    data_classification: DataClassification = "internal"
    owner: str | None = None
    freshness_sla: str | None = None
    allowed_personas: tuple[str, ...] = ()
    requires_evidence: bool = False

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
        if self.data_classification not in ALLOWED_DATA_CLASSIFICATIONS:
            raise ValueError(
                f"Subagent {self.name!r} has unsupported data_classification "
                f"{self.data_classification!r}. Allowed: {sorted(ALLOWED_DATA_CLASSIFICATIONS)}"
            )
        if not self.description:
            raise ValueError(f"Subagent {self.name!r} must include a description")
        if self.kind == "genie" and not self.space_id:
            raise ValueError(f"Genie subagent {self.name!r} must define space_id")
        if self.kind != "genie" and not self.endpoint:
            raise ValueError(f"Non-genie subagent {self.name!r} must define endpoint")
        if any(not persona.strip() for persona in self.allowed_personas):
            raise ValueError(f"Subagent {self.name!r} has invalid allowed_personas entry")

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
        allowed_personas_raw = value.get("allowed_personas", [])
        if not isinstance(allowed_personas_raw, list) or not all(
            isinstance(item, str) for item in allowed_personas_raw
        ):
            raise ValueError(
                f"Subagent {value.get('name', '<unknown>')!r} allowed_personas must be a list of strings"
            )
        try:
            return cls(
                name=value["name"],
                kind=kind,
                description=value["description"],
                endpoint=value.get("endpoint"),
                space_id=value.get("space_id"),
                auth_mode=auth_mode,
                data_classification=value.get("data_classification", "internal"),
                owner=value.get("owner"),
                freshness_sla=value.get("freshness_sla"),
                allowed_personas=tuple(allowed_personas_raw),
                requires_evidence=bool(value.get("requires_evidence", False)),
            )
        except KeyError as exc:
            raise ValueError(f"Subagent config missing required key: {exc}") from exc


def parse_subagents(raw_subagents: Iterable[dict[str, Any]]) -> list[SubagentConfig]:
    """Parse and validate raw subagent dictionaries into typed models."""
    return [SubagentConfig.from_dict(value) for value in raw_subagents]


DEFAULT_SUBAGENTS_CONFIG_PATH = Path(__file__).with_name("subagents.json")
SUBAGENTS_CONFIG_PATH_ENV = "SUBAGENTS_CONFIG_PATH"


def load_subagents(config_path: str | Path | None = None) -> list[SubagentConfig]:
    """Load and validate subagent configuration from JSON file."""
    resolved_path = Path(
        config_path or os.getenv(SUBAGENTS_CONFIG_PATH_ENV) or DEFAULT_SUBAGENTS_CONFIG_PATH
    )
    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Subagent configuration file not found: {resolved_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Subagent configuration file contains invalid JSON: {resolved_path}"
        ) from exc

    if not isinstance(raw, list):
        raise ValueError(f"Subagent configuration root must be a list: {resolved_path}")
    if not all(isinstance(item, dict) for item in raw):
        raise ValueError(f"Each subagent entry must be an object: {resolved_path}")

    return parse_subagents(raw)


SUBAGENTS = load_subagents()
