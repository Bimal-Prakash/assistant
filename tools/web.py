import re
import requests
import logging

logger = logging.getLogger("jarvis.web")

def search_web(query: str) -> str:
    """Searches duckduckgo and returns top text snippets."""
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    data = {"q": query}
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        
        # Regex to find snippet texts
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', response.text, re.IGNORECASE | re.DOTALL)
        
        if not snippets:
            return "No results found for your query."
        
        # Clean HTML tags and newlines
        clean_snippets = []
        for s in snippets[:3]:  # Return top 3 snippets to keep context small
            s = re.sub(r'<[^>]+>', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            if s:
                clean_snippets.append(s)
                
        if not clean_snippets:
            return "No text snippets found."
            
        result_text = "\n".join(f"- {s}" for s in clean_snippets)
        return f"Web Search Results for '{query}':\n{result_text}"
        
    except Exception as e:
        logger.exception("Web search failed")
        return f"Web search failed: {e}"
