"""Chat command parsing and token-display helpers."""


def parse_token_command(
    text: str,
    set_token_command: str,
    clear_token_command: str,
) -> tuple[str | None, str | None]:
    """Parse token management commands from user input."""
    stripped = text.strip()
    if stripped == clear_token_command:
        return ("clear", None)
    if not stripped.startswith(f"{set_token_command} "):
        return (None, None)
    token = stripped[len(set_token_command) :].strip()
    return ("set", token)


def mask_token(token: str) -> str:
    """Mask a token value for safe user-visible confirmation text."""
    cleaned = token.strip()
    if len(cleaned) <= 10:
        return "*" * len(cleaned)
    return f"{cleaned[:6]}...{cleaned[-4:]}"
