"""Typed service interfaces used for dependency injection and testing."""

from typing import Any, Protocol

from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.types.responses import ResponsesAgentRequest

from backend.domain.subagent_config import SubagentConfig
from backend.shared.runtime_utils import RequestIdentityContext


class IdentityContextProvider(Protocol):
    """Returns request identity context for app and OBO execution paths."""

    def __call__(self) -> RequestIdentityContext: ...


class SessionIdProvider(Protocol):
    """Extracts session id from an incoming request payload."""

    def __call__(self, request: ResponsesAgentRequest) -> str | None: ...


class TraceMetadataUpdater(Protocol):
    """Persists trace metadata for observability."""

    def __call__(self, metadata: dict[str, str]) -> Any: ...


class OboClientFactory(Protocol):
    """Builds a user-scoped Databricks OpenAI client for OBO execution."""

    def __call__(self, workspace_client: Any) -> AsyncDatabricksOpenAI: ...


class SubagentToolsBuilder(Protocol):
    """Builds function tools for configured non-Genie subagents."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
    ) -> list: ...


class McpServersBuilder(Protocol):
    """Builds MCP servers and unavailable tool list for current identity context."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        identity_ctx: RequestIdentityContext,
    ) -> tuple[list[McpServer], list[str]]: ...


class FunctionToolWrapper(Protocol):
    """Wraps an async callable as an agent function tool."""

    def __call__(self, func: Any) -> Any: ...


class McpServerFactory(Protocol):
    """Builds an MCP server instance from connection details."""

    def __call__(self, *, url: str, name: str, workspace_client: Any) -> McpServer: ...


class MessageBus(Protocol):
    """Publishes typed lifecycle events for agent request execution."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None: ...
