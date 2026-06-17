import os
import glob
import logging
from pathlib import Path

# Load environment variables
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

try:
    # pyrefly: ignore [missing-import]
    import chromadb
    # pyrefly: ignore [missing-import]
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
except ImportError:
    print("Error: chromadb is not installed. Run 'pip install chromadb'.")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index_obsidian")

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import OLLAMA_API_URL

def chunk_text(text: str, max_words: int = 150) -> list[str]:
    """Splits text into chunks of roughly max_words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
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
    
    # Find all markdown files
    md_files = glob.glob(os.path.join(vault_path, "**/*.md"), recursive=True)
    logger.info(f"Found {len(md_files)} markdown files in vault. Processing...")

    documents = []
    metadatas = []
    ids = []
    
    for file_path in md_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            filename = os.path.basename(file_path)
            
            # Chunk the file
            chunks = chunk_text(content)
            for idx, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({"filename": filename, "path": file_path, "chunk": idx})
                ids.append(f"{filename}_{idx}")
                
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")

    if not documents:
        logger.warning("No text found to index.")
        return

    # Upsert in batches to avoid overwhelming Ollama
    batch_size = 100
    total_chunks = len(documents)
    
    logger.info(f"Generated {total_chunks} chunks. Embedding and saving to ChromaDB...")
    
    for i in range(0, total_chunks, batch_size):
        end = min(i + batch_size, total_chunks)
        logger.info(f"Indexing batch {i} to {end}...")
        collection.upsert(
            documents=documents[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end]
        )
        
    logger.info("Successfully indexed all notes into VectorDB!")

if __name__ == "__main__":
    main()
