import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run_command(cmd: list, description: str):
    logger.info(f"Starting: {description}...")
    try:
        # We use check=True to raise an exception if it fails
        subprocess.run(cmd, check=True)
        logger.info(f"✅ Success: {description}")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed: {description}")
        logger.error(f"Command '{' '.join(cmd)}' returned non-zero exit status {e.returncode}.")
    except FileNotFoundError:
        logger.error(f"❌ Failed: {description}")
        logger.error(f"Executable not found for command: {cmd[0]}. Please ensure it is installed and on your PATH.")

def install_spacy_models():
    try:
        # pyrefly: ignore [missing-import]
        import spacy
        logger.info("Spacy is installed. Downloading 'en_core_web_sm' model...")
        # pyrefly: ignore [missing-import]
        from spacy.cli import download
        download("en_core_web_sm")
        logger.info("✅ Success: Spacy model downloaded.")
    except ImportError:
        logger.warning("⚠️ Spacy is not installed. Skipping spacy model download.")
    except Exception as e:
        logger.error(f"❌ Failed to download spacy model: {e}")

def pull_ollama_models():
    # We pull the models using the ollama CLI
    models = ["qwen2.5:3b", "nomic-embed-text"]
    for model in models:
        run_command(["ollama", "pull", model], f"Pulling Ollama model '{model}'")

def main():
    print("="*50)
    print("🚀 Jarvis Offline Agent - Model Setup")
    print("="*50)
    
    print("\n[1/2] Checking Spacy NLP Models...")
    install_spacy_models()
    
    print("\n[2/2] Checking Ollama Local Models...")
    logger.info("Please ensure Ollama is installed and running in the background.")
    pull_ollama_models()
    
    print("\n" + "="*50)
    print("🎉 All background models and dependencies have been processed!")
    print("You are ready to run Jarvis: `python run.py --text`")
    print("="*50)

if __name__ == "__main__":
    main()
