"""Execute PowerShell commands on the PC.

Dangerous commands (delete, format, kill process) are blocked and
return CONFIRMATION_REQUIRED so the agent asks the user to confirm.
"""

import subprocess

SENSITIVE_KEYWORDS = [
    "rm ", "del ", "remove-item", "format", "uninstall",
    "stop-process", "kill", "rmdir", "rd ", "erase",
    "clear-content", "set-content", "out-file",
    "move-item", "rename-item",
]


def exec_run_terminal(command: str) -> str:
    if not command:
        return "Error: command is required."

    cmd_lower = command.lower()
    if any(kw in cmd_lower for kw in SENSITIVE_KEYWORDS):
        return (
            f"CONFIRMATION_REQUIRED: This is a sensitive command: {command}. "
            "Ask the user to confirm before running it."
        )

    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip()
        err = result.stderr.strip()
        if err:
            return f"Output:\n{output}\nError:\n{err}"
        return f"Output:\n{output}" if output else "Command executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 15 seconds."
    except Exception as e:
        return f"Error running command: {e}"
