import os
# pyrefly: ignore [missing-import]
import chromadb
# pyrefly: ignore [missing-import]
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

class SemanticRouter:
    def __init__(self):
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db_router")
        
        # Ensure directory exists to avoid errors
        os.makedirs(db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=db_path)
        from core.config import OLLAMA_API_URL
        # Remove the /api/generate part if it exists to get the base URL
        base_url = OLLAMA_API_URL.replace("/api/generate", "")
        self.ef = OllamaEmbeddingFunction(
            model_name="nomic-embed-text",
            url=f"{base_url}/api/embeddings"
        )
        
        # L2 distance is default
        self.collection = self.client.get_or_create_collection(
            name="intents", 
            embedding_function=self.ef
        )
        self._seed_intents()

    def _seed_intents(self):
        """Seed the collection with common intent phrases."""
        # Always drop and recreate the collection to ensure new intents are loaded during this upgrade
        try:
            self.client.delete_collection("intents")
        except Exception:
            pass
            
        self.collection = self.client.get_or_create_collection(
            name="intents", 
            embedding_function=self.ef
        )

        intents = {
            "OPEN_APP": [
                "open spotify", "launch google chrome", "start notepad", 
                "can you open discord", "boot up vs code", "open whatsapp",
                "open the camera", "launch calculator", "open word",
                "open the app", "start the program"
            ],
            "CLOSE_APP": [
                "close spotify", "kill google chrome", "quit notepad",
                "shut down discord", "exit vs code", "close the window",
                "kill the app", "close the application", "close word"
            ],
            "MEDIA_CONTROL_PLAYPAUSE": [
                "play the music", "pause the song", "stop the music", "play it",
                "pause it", "play pause", "pause", "play"
            ],
            "MEDIA_CONTROL_NEXT": [
                "skip this track", "next song", "next track", "skip song"
            ],
            "MEDIA_CONTROL_PREV": [
                "go back", "previous song", "previous track", "last song"
            ],
            "MINIMIZE_APP": [
                "minimize the window", "minimise the app", "minimize this", "minimise"
            ],
            "WHATSAPP_CALL": [
                "call mom", "call Bimal", "can you call John", "make a phone call",
                "call my best friend", "call someone", "ring john", "voice call"
            ],
            "CONVERSATIONAL_TRAP": [
                "what is my hobby", "who is my favorite artist", "how are you",
                "what is your name", "who am I", "tell me a joke", "search the web",
                "what do i like", "can you answer a question", "hello", "jarvis",
                "play juicewrlds song", "play my favorite artist", "play taylor swift",
                "are you conscious", "do you know who that is", "who is that",
                "what does jarvis mean", "what are you", "how do you work",
                "thank you jarvis now you can shutdown", "now you can shutdown",
                "close that"
            ]
        }

        docs = []
        ids = []
        metas = []
        idx = 0
        for intent, phrases in intents.items():
            for phrase in phrases:
                docs.append(phrase)
                ids.append(f"intent_{idx}")
                metas.append({"intent": intent})
                idx += 1

        print("[SemanticRouter] Seeding intent vectors for the first time...")
        self.collection.add(documents=docs, metadatas=metas, ids=ids)
        print("[SemanticRouter] Intent seeding complete.")

    def route(self, command: str):
        """
        Takes a raw command and returns the matched intent string, or None if unknown.
        """
        try:
            results = self.collection.query(
                query_texts=[command],
                n_results=1
            )
            
            if results and results["distances"] and results["distances"][0]:
                distance = results["distances"][0][0]
                intent = results["metadatas"][0][0]["intent"]
                
                print(f"[SemanticRouter] Matched '{intent}' with distance: {distance:.2f}")
                
                # Dynamic Thresholds
                if "MEDIA_CONTROL" in intent:
                    threshold = 0.20
                elif intent == "OPEN_APP":
                    threshold = 0.15  # Ultra strict to prevent "on spotify" from matching "open spotify"
                else:
                    threshold = 0.45
                
                if distance < threshold:
                    if intent == "CONVERSATIONAL_TRAP":
                        return None
                    return intent
            return None
        except Exception as e:
            print(f"[SemanticRouter] Error routing command: {e}")
            return None
