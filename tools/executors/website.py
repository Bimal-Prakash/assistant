"""Open a website in the default browser."""

import json


def exec_open_website(url: str) -> str:
    if not url:
        return "Error: URL is required."
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return json.dumps({"_client_action": "open_website", "url": url})
