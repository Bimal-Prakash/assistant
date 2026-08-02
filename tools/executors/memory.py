"""Memory tools — remember and recall facts about the user."""


def exec_remember_fact(key: str, value: str) -> str:
    from tools.executors.obsidian import get_vault_path
    from core.redactor import privacy_filter
    import os
    
    # Scrub sensitive text before saving
    safe_key = privacy_filter.scrub(key)
    safe_value = privacy_filter.scrub(value)
    
    vault_path = get_vault_path()
    if not vault_path or not os.path.exists(vault_path):
        return f"Error: Obsidian vault not found at '{vault_path}'. Cannot remember fact."
        
    pref_file = os.path.join(vault_path, "learned_preferences.md")
    
    try:
        if not os.path.exists(pref_file):
            with open(pref_file, "w", encoding="utf-8") as f:
                f.write("# Learned Preferences\n\nThis file stores facts and preferences learned by the assistant.\n\n")
                
        with open(pref_file, "a", encoding="utf-8") as f:
            f.write(f"- **{safe_key}**: {safe_value}\n")
            
        return f"Successfully remembered: {safe_key} = {safe_value} in your Obsidian vault."
    except Exception as e:
        return f"Failed to remember fact due to error: {e}"


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

def exec_semantic_search_chat_history(query: str) -> str:
    """
    Search your conversation history using semantic vector search.
    Useful when recalling tasks or commands you were asked about in the past.
    """
    import os
    try:
        # pyrefly: ignore [missing-import]
        import chromadb
        # pyrefly: ignore [missing-import]
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    except ImportError:
        return "Error: chromadb is not installed."
        
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db_chat")
    if not os.path.exists(db_path):
        return "I don't have any past conversation history recorded yet."
        
    try:
        client = chromadb.PersistentClient(path=db_path)
        from core.config import OLLAMA_API_URL
        base_url = OLLAMA_API_URL.replace("/api/generate", "")
        ef = OllamaEmbeddingFunction(
            model_name="nomic-embed-text",
            url=f"{base_url}/api/embeddings"
        )
        
        collection = client.get_collection(name="chat_history", embedding_function=ef)
        
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if not results["documents"] or not results["documents"][0]:
            return f"No matches found in conversation history for '{query}'."
            
        output = [f"Found these previous conversation turns related to '{query}':\n"]
        
        # Sort by timestamp to give chronological order
        docs = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            docs.append((meta["timestamp"], doc))
            
        docs.sort(key=lambda x: x[0])
        
        for ts, doc in docs:
            output.append(doc)
            
        return "\n".join(output)
        
    except Exception as e:
        return f"Error searching chat history: {e}"

def exec_search_memory(query: str) -> str:
    """
    Search both Conversation History and Obsidian Notes in parallel for maximum speed.
    """
    import concurrent.futures
    from tools.executors.obsidian import exec_semantic_search_obsidian
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_chat = executor.submit(exec_semantic_search_chat_history, query)
        future_obsidian = executor.submit(exec_semantic_search_obsidian, query)
        
        chat_res = future_chat.result()
        obsidian_res = future_obsidian.result()
        
    output = []
    
    # Check if chat history returned actual results
    if "No matches found" not in chat_res and "I don't have any past conversation history" not in chat_res and "Error" not in chat_res:
        output.append("=== RECENT CONVERSATIONS ===")
        output.append(chat_res)
        
    # Check if obsidian returned actual results
    if "No semantic matches found" not in obsidian_res and "Error" not in obsidian_res:
        output.append("=== PERSONAL KNOWLEDGE (OBSIDIAN) ===")
        output.append(obsidian_res)
        
    if not output:
        return f"I couldn't find any information about '{query}' in either your conversations or your personal notes. (Hint: Do not repeat this search. Use final_answer to tell the user you don't know.)"
        
    return "\n\n".join(output)
