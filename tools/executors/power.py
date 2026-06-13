"""Power control tool — shutdown/restart require confirmation."""

SENSITIVE_ACTIONS = {"shutdown", "restart"}


def exec_power_control(type: str) -> str:
    t = type.strip().lower()
    if t in SENSITIVE_ACTIONS:
        return (
            f"CONFIRMATION_REQUIRED: {t.title()} is a sensitive action. "
            "Ask the user to confirm before proceeding."
        )
    from tools.system.power import power_control
    return power_control(t, delay_seconds=3)
