"""Shared backend utilities for session handling, workspace access, and streaming."""

from dataclasses import dataclass
import logging
from typing import AsyncGenerator, AsyncIterator, Optional
from uuid import uuid4

from agents.result import StreamEvent
from databricks.sdk import WorkspaceClient
from mlflow.genai.agent_server import get_request_headers
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentStreamEvent

FORWARDED_ACCESS_TOKEN_HEADER = "x-forwarded-access-token"


@dataclass(frozen=True)
class RequestIdentityContext:
    """Per-request identity context for hybrid app and OBO authorization."""

    app_workspace_client: WorkspaceClient
    user_workspace_client: WorkspaceClient | None
    forwarded_access_token: str | None

    @property
    def has_user_identity(self) -> bool:
        return bool(self.user_workspace_client and self.forwarded_access_token)


def get_session_id(request: ResponsesAgentRequest) -> str | None:
    """Extract a stable session identifier from request context or custom inputs.

    Args:
        request: Incoming Responses request.

    Returns:
        Session identifier when present; otherwise None.
    """
    if request.context and request.context.conversation_id:
        return request.context.conversation_id
    if request.custom_inputs and isinstance(request.custom_inputs, dict):
        return request.custom_inputs.get("session_id")
    return None


def get_databricks_host(workspace_client: WorkspaceClient | None = None) -> Optional[str]:
    """Resolve the Databricks workspace host from client configuration.

    Args:
        workspace_client: Optional preconfigured workspace client.

    Returns:
        Workspace host URL when available; otherwise None.
    """
    workspace_client = workspace_client or WorkspaceClient()
    try:
        return workspace_client.config.host
    except Exception as e:
        logging.exception(f"Failed to resolve Databricks host from environment: {e}")
        return None


def build_mcp_url(path: str, workspace_client: WorkspaceClient | None = None) -> str:
    """Build an absolute MCP URL from a workspace-relative path.

    Args:
        path: Absolute URL or workspace-relative API path.
        workspace_client: Optional preconfigured workspace client.

    Returns:
        Absolute MCP URL or the original input when already absolute.
    """
    if not path.startswith("/"):
        return path
    hostname = get_databricks_host(workspace_client)
    return f"{hostname}{path}"


def get_user_workspace_client() -> WorkspaceClient:
    """Create a workspace client authenticated with the forwarded user token.

    Returns:
        Workspace client configured for on-behalf-of-user access.
    """
    token = get_forwarded_access_token()
    if not token:
        raise ValueError(
            f"Missing required forwarded access token header: {FORWARDED_ACCESS_TOKEN_HEADER}"
        )
    return WorkspaceClient(token=token, auth_type="pat")


def get_forwarded_access_token() -> str | None:
    """Get the forwarded user token from inbound request headers."""
    headers = get_request_headers() or {}
    token = headers.get(FORWARDED_ACCESS_TOKEN_HEADER)
    if not token:
        return None
    stripped = token.strip()
    return stripped or None


def build_request_identity_context() -> RequestIdentityContext:
    """Build per-request app and user identity clients for hybrid authorization."""
    app_workspace_client = WorkspaceClient()
    token = get_forwarded_access_token()
    user_workspace_client = (
        WorkspaceClient(token=token, auth_type="pat") if token else None
    )
    return RequestIdentityContext(
        app_workspace_client=app_workspace_client,
        user_workspace_client=user_workspace_client,
        forwarded_access_token=token,
    )


async def process_agent_stream_events(
    async_stream: AsyncIterator[StreamEvent],
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Normalize stream event item IDs for downstream consumers.

    Args:
        async_stream: Async iterator of raw agent stream events.

    Yields:
        Responses-compatible stream events with stable item identifiers.
    """
    curr_item_id = str(uuid4())
    async for event in async_stream:
        if event.type == "raw_response_event":
            event_data = event.data.model_dump()
            if event_data["type"] == "response.output_item.added":
                curr_item_id = str(uuid4())
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item") is not None and event_data["item"].get("id") is not None:
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item_id") is not None:
                event_data["item_id"] = curr_item_id
            yield event_data
        elif event.type == "run_item_stream_event" and event.item.type == "tool_call_output_item":
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=event.item.to_input_item(),
            )
