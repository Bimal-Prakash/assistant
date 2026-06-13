"""Memory tools — remember and recall facts about the user."""


def exec_remember_fact(key: str, value: str) -> str:
    from server.dependencies import MEMORY_STORE
    ok = MEMORY_STORE.set_fact(
        client="pc",
        fact_key=key.strip().lower(),
        fact_value=value.strip(),
    )
    if ok:
        return f"Remembered: {key} = {value}"
    return f"Failed to remember {key}."


def exec_recall_fact(key: str) -> str:
    from server.dependencies import MEMORY_STORE
    value = MEMORY_STORE.get_fact(client="pc", fact_key=key.strip().lower())
    if value:
        return f"{key}: {value}"
    return f"I don't have any information stored for '{key}'."


def exec_recall_last_command(**kwargs) -> str:
    from server.dependencies import MEMORY_STORE
    text = MEMORY_STORE.get_last_user_text(client="pc")
    if text:
        return f"Your last command was: {text}"
    return "I don't have a previous command saved."
