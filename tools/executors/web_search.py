"""Search the web using DuckDuckGo."""

from tools.web import search_web as _search_web


def exec_search_web(query: str) -> str:
    if not query:
        return "Error: search query is required."
    return _search_web(query)
