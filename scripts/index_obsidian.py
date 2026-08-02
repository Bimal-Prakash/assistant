import os
import glob
import logging
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    import chromadb
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
except ImportError:
    print("Error: chromadb is not installed. Run 'pip install chromadb'.")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index_obsidian")

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import OLLAMA_API_URL

def chunk_text(text: str, max_words: int = 150, overlap_words: int = 30) -> list[str]:
    """Splits text into chunks of roughly max_words, with overlap."""
    words = text.split()
    chunks = []
    if not words:
        return chunks
    
    step = max(1, max_words - overlap_words)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + max_words])
        if chunk.strip():
            chunks.append(chunk)
            
    return chunks

def main():
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        logger.error("OBSIDIAN_VAULT_PATH is not set in your .env file.")
        return

    if not os.path.isdir(vault_path):
        logger.error(f"Obsidian vault path '{vault_path}' does not exist.")
        return

    logger.info("Connecting to local ChromaDB...")
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
    client = chromadb.PersistentClient(path=db_path)

    # Configure Ollama embeddings
    logger.info("Initializing Ollama embedding function (nomic-embed-text)...")
    base_url = OLLAMA_API_URL.replace("/api/generate", "")
    ef = OllamaEmbeddingFunction(
        model_name="nomic-embed-text",
        url=f"{base_url}/api/embeddings"
    )

    collection = client.get_or_create_collection(
        name="obsidian_notes",
        embedding_function=ef
    )

    cache_file = os.path.join(db_path, "vault_cache.json")
    filename_cache_file = os.path.join(db_path, "filename_to_path.json")
    
    vault_cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                vault_cache = json.load(f)
        except Exception:
            pass

    md_files = glob.glob(os.path.join(vault_path, "**/*.md"), recursive=True)
    
    current_files = set()
    filename_to_path = {}
    
    documents_to_upsert = []
    metadatas_to_upsert = []
    ids_to_upsert = []
    
    files_to_delete = []

    for file_path in md_files:
        current_files.add(file_path)
        filename = os.path.basename(file_path)
        if filename.startswith("JARVIS_THOUGHTS"):
            continue
            
        filename_to_path[filename.lower()] = file_path
            
        mtime = os.path.getmtime(file_path)
        
        if file_path in vault_cache and vault_cache[file_path].get("mtime") == mtime:
            continue
            
        if file_path in vault_cache:
            files_to_delete.append(file_path)
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            chunks = chunk_text(content)
            for idx, chunk in enumerate(chunks):
                documents_to_upsert.append(chunk)
                metadatas_to_upsert.append({"filename": filename, "path": file_path, "chunk": idx})
                ids_to_upsert.append(f"{filename}_{idx}")
                
            vault_cache[file_path] = {"mtime": mtime, "chunks": len(chunks)}
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")

    for cached_file in list(vault_cache.keys()):
        if cached_file not in current_files:
            files_to_delete.append(cached_file)
            del vault_cache[cached_file]

    if files_to_delete:
        logger.info(f"Removing {len(files_to_delete)} deleted/modified files from ChromaDB...")
        for file_path in files_to_delete:
            try:
                collection.delete(where={"path": file_path})
            except Exception as e:
                pass

    if documents_to_upsert:
        batch_size = 20
        total_chunks = len(documents_to_upsert)
        logger.info(f"Generated {total_chunks} new/modified chunks. Embedding and saving to ChromaDB...")

        for i in range(0, total_chunks, batch_size):
            end = min(i + batch_size, total_chunks)
            logger.info(f"Indexing batch {i} to {end}...")
            collection.upsert(
                documents=documents_to_upsert[i:end],
                metadatas=metadatas_to_upsert[i:end],
                ids=ids_to_upsert[i:end]
            )

    os.makedirs(db_path, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(vault_cache, f)
    with open(filename_cache_file, "w", encoding="utf-8") as f:
        json.dump(filename_to_path, f)

    logger.info("Successfully updated Obsidian index!")

if __name__ == "__main__":
    main()
