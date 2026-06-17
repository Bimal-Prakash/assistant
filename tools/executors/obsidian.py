"""
Obsidian Integration Executors.

Tools for searching and reading markdown files from an Obsidian vault.
"""

import os
import glob
import logging
from typing import Optional
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("jarvis.tools.executors.obsidian")

def get_vault_path() -> Optional[str]:
    return os.getenv("OBSIDIAN_VAULT_PATH")

def exec_search_obsidian(query: str) -> str:
    """
    Search all markdown files in the Obsidian vault for a specific query.
    Returns a summary of matched files and snippets.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return "Error: OBSIDIAN_VAULT_PATH is not set in the environment variables."

    if not os.path.exists(vault_path):
        return f"Error: The Obsidian vault path '{vault_path}' does not exist."

    query_lower = query.lower()
    matches = []
    
    # Recursively find all markdown files
    search_pattern = os.path.join(vault_path, "**", "*.md")
    for file_path in glob.glob(search_pattern, recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            if query_lower in content.lower():
                # Extract a snippet around the first match
                idx = content.lower().find(query_lower)
                start = max(0, idx - 40)
                end = min(len(content), idx + len(query) + 40)
                snippet = content[start:end].replace('\n', ' ').strip()
                
                rel_path = os.path.relpath(file_path, vault_path)
                matches.append(f"- **{rel_path}**: \"...{snippet}...\"")
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            continue

    if not matches:
        return f"No results found in your Obsidian vault for '{query}'."

    # Limit results if there are too many
    max_results = 10
    response = "Found matches in the following notes:\n" + "\n".join(matches[:max_results])
    if len(matches) > max_results:
        response += f"\n...and {len(matches) - max_results} more files."
        
    return response

def exec_read_obsidian_note(note_name: str) -> str:
    """
    Read the content of a specific Obsidian note by name.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return "Error: OBSIDIAN_VAULT_PATH is not set in the environment variables."

    if not os.path.exists(vault_path):
        return f"Error: The Obsidian vault path '{vault_path}' does not exist."

    # Ensure the note name ends with .md
    if not note_name.lower().endswith('.md'):
        note_name += '.md'

    # Search for the file in the vault
    search_pattern = os.path.join(vault_path, "**", "*.md")
    matched_file = None
    
    for file_path in glob.glob(search_pattern, recursive=True):
        if os.path.basename(file_path).lower() == note_name.lower():
            matched_file = file_path
            break

    if not matched_file:
        return f"Error: Note '{note_name}' not found in the Obsidian vault."

    try:
        with open(matched_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        rel_path = os.path.relpath(matched_file, vault_path)
        # Limit the content length to avoid overflowing the LLM context
        max_length = 3000
        if len(content) > max_length:
            content = content[:max_length] + "\n\n...[Content truncated for length]..."
            
        return f"Content of '{rel_path}':\n\n{content}"
    except Exception as e:
        logger.exception(f"Failed to read note {matched_file}")
        return f"Error reading the note: {e}"

def exec_semantic_search_obsidian(query: str) -> str:
    """
    Search the Obsidian vault using semantic vector search.
    Returns the most relevant chunks of text.
    """
    try:
        # pyrefly: ignore [missing-import]
        import chromadb
        # pyrefly: ignore [missing-import]
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    except ImportError:
        return "Error: chromadb is not installed."
        
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")
    if not os.path.exists(db_path):
        return "Error: Vector database not found. Please run scripts/index_obsidian.py first."
        
    try:
        client = chromadb.PersistentClient(path=db_path)
        from core.config import OLLAMA_API_URL
        base_url = OLLAMA_API_URL.replace("/api/generate", "")
        ef = OllamaEmbeddingFunction(
            model_name="nomic-embed-text",
            url=f"{base_url}/api/embeddings"
        )
        
        collection = client.get_collection(name="obsidian_notes", embedding_function=ef)
        
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if not results["documents"] or not results["documents"][0]:
            return f"No semantic matches found for '{query}'."
            
        output = [f"Semantic Search Results for '{query}':\n"]
        
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            filename = metadata.get("filename", "Unknown file")
            output.append(f"--- From {filename} ---")
            output.append(doc)
            output.append("")
            
        return "\n".join(output)
        
    except Exception as e:
        logger.exception("Failed semantic search")
        return f"Error during semantic search: {e}"
