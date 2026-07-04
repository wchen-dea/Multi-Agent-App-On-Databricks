"""Presentation-oriented content builders for the Chainlit UI."""

import chainlit as cl

from frontend.app.session import persona_status_line, token_status_line


def welcome_message(
    company_name: str,
    company_tagline: str,
    chat_greeting: str,
    set_token_command: str,
    clear_token_command: str,
    set_persona_command: str,
    clear_persona_command: str,
    allowed_personas: tuple[str, ...],
) -> str:
    """Build the branded welcome panel shown at chat start."""
    persona_list = ", ".join(allowed_personas)
    return (
        f"## {company_name} AI Workspace\n"
        f"{company_tagline}\n\n"
        f"{chat_greeting}\n\n"
        "### Persona Selection\n"
        "Pick a persona from the starter cards below, or run a command manually:\n"
        f"- `{set_persona_command} <persona>`\n"
        f"- `{clear_persona_command}`\n"
        f"Accepted personas: {persona_list}\n\n"
        "### What I can help with\n"
        "- Query business insights through Genie spaces\n"
        "- Route requests to specialist serving endpoint agents\n"
        "- Coordinate cross-tool workflows in one conversation\n\n"
        "### Session Commands\n"
        f"- `{set_token_command} <databricks_access_token>`: enable OBO token forwarding\n"
        f"- `{clear_token_command}`: disable OBO token forwarding for this session\n\n"
        "Tip: set persona first, then ask your question.\n\n"
        f"{token_status_line()}\n"
        f"{persona_status_line()}"
    )


def starter_prompts() -> list[cl.Starter]:
    """Return curated starter prompts for common enterprise workflows."""
    return [
        cl.Starter(
            label="Set Persona: Manager",
            message="/persona manager",
        ),
        cl.Starter(
            label="Set Persona: Analyst",
            message="/persona analyst",
        ),
        cl.Starter(
            label="Set Persona: Operator",
            message="/persona operator",
        ),
        cl.Starter(
            label="Set Persona: Engineer",
            message="/persona engineer",
        ),
        cl.Starter(
            label="Sales Pulse",
            message="Summarize weekly sales trends and highlight top 3 drivers.",
        ),
        cl.Starter(
            label="Top 5 Stores",
            message="Use sales data and format the top 5 stores by revenue with rank, store, revenue, delta WoW, and one-line insight.",
        ),
        cl.Starter(
            label="Knowledge Lookup",
            message="Find the latest policy for production rollout approvals.",
        ),
        cl.Starter(
            label="Ops Health Check",
            message="Give me an operations health snapshot and active risks.",
        ),
    ]


def source_badge_line(categories: set[str], tools: set[str]) -> str:
    """Build a markdown provenance footer for an assistant response."""
    if not categories and not tools:
        return ""

    parts: list[str] = []
    if categories:
        parts.append("Sources used: " + " | ".join(sorted(categories)))
    if tools:
        parts.append("Tools: " + " | ".join(sorted(format_tool_label(name) for name in tools)))

    return "\n\n---\n" + "\n".join(parts)


def session_status_badge_line(persona: str | None, token_forwarding_enabled: bool) -> str:
    """Build a session status footer with persona and auth mode."""
    persona_label = persona or "not set"
    auth_mode = "hybrid (app + OBO token)" if token_forwarding_enabled else "app-only"
    return "\n\n---\nSession: persona=`{}` | auth=`{}`".format(persona_label, auth_mode)


def format_tool_label(tool_name: str) -> str:
    """Convert internal tool identifiers to user-friendly display names."""
    if tool_name.startswith("query_"):
        return tool_name[len("query_") :].replace("_", " ").title()
    return tool_name.replace("_", " ").title()
