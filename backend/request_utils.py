"""Normalize request payloads and extract MCP-aware errors."""

from typing import Any

from agents.exceptions import UserError


def to_messages(input_items) -> list[dict[str, Any]]:
    """Normalize MLflow response items to plain role/content dictionaries.

    Args:
        input_items: MLflow input items from a Responses request.

    Returns:
        List of plain role/content dictionaries.
    """
    messages = []
    for item in input_items:
        data = item.model_dump() if hasattr(item, "model_dump") else item
        if not isinstance(data, dict):
            continue

        role = data.get("role")
        if not role:
            continue

        content = data.get("content", "")
        if isinstance(content, list):
            texts = [
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            ]
            content = " ".join(filter(None, texts))

        messages.append({"role": role, "content": content})

    return messages


def extract_mcp_errors(exc: Exception) -> list[UserError]:
    """Extract UserError instances from direct exceptions or ExceptionGroups.

    Args:
        exc: Raised exception captured from handler execution.

    Returns:
        List of UserError instances found within the exception.
    """
    if isinstance(exc, UserError):
        return [exc]
    if isinstance(exc, BaseExceptionGroup):
        return [err for err in exc.exceptions if isinstance(err, UserError)]
    return []
