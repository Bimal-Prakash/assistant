import os
import math
import collections
import re
import time
# pyrefly: ignore [missing-import]
import chromadb
# pyrefly: ignore [missing-import]
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

class FastTFIDF:
    def __init__(self):
        self.documents = []
        self.labels = []
        self.vocab = {}
        self.idf = {}
        self.doc_vectors = []

    def _tokenize(self, text):
        return re.findall(r'\b\w+\b', text.lower())

    def fit(self, intents_dict):
        for label, phrases in intents_dict.items():
            for phrase in phrases:
                self.documents.append(self._tokenize(phrase))
                self.labels.append(label)

        df = collections.defaultdict(int)
        for doc in self.documents:
            unique_words = set(doc)
            for word in unique_words:
                if word not in self.vocab:
                    self.vocab[word] = len(self.vocab)
                df[word] += 1

        N = len(self.documents)
        for word, count in df.items():
            self.idf[word] = math.log((1 + N) / (1 + count)) + 1

        for doc in self.documents:
            vec = self._compute_tfidf_vector(doc)
            self.doc_vectors.append(vec)

    def _compute_tfidf_vector(self, tokens, is_query=False):
        tf = collections.defaultdict(int)
        for t in tokens:
            tf[t] += 1
        vec = {}
        norm_sq = 0.0
        
        # Calculate default IDF for out-of-vocabulary words
        N = len(self.documents)
        default_idf = math.log((1 + N) / 1.0) + 1.0

        for word, count in tf.items():
            if word in self.idf:
                val = count * self.idf[word]
                vec[self.vocab[word]] = val
                norm_sq += val * val
            elif is_query:
                val = count * default_idf
                norm_sq += val * val

        norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
        return {idx: val / norm for idx, val in vec.items()}

    def predict(self, text, threshold=0.4):
        tokens = self._tokenize(text)
        query_vec = self._compute_tfidf_vector(tokens, is_query=True)
        if not query_vec:
            return None, 0.0

        best_score = -1.0
        best_label = None
        for doc_vec, label in zip(self.doc_vectors, self.labels):
            score = sum(query_vec.get(idx, 0) * val for idx, val in doc_vec.items())
            if score > best_score:
                best_score = score
                best_label = label

        if best_score >= threshold:
            return best_label, best_score
        return None, best_score

class SemanticRouter:
    # Common intents definition
    INTENTS = {
        "OPEN_APP": [
            "open spotify", "launch google chrome", "start notepad",
            "can you open discord", "boot up vs code", "open whatsapp",
            "open the camera", "launch calculator", "open word",
            "open the app", "start the program"
        ],
        "CLOSE_APP": [
            "close spotify", "kill google chrome", "quit notepad",
            "shut down discord", "exit vs code", "close the window",
            "kill the app", "close the application", "close word",
            "close whatsapp", "close it", "close telegram", "quit app"
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
            "minimize the window", "minimise the app", "minimize this", "minimise",
            "minimize whatsapp", "minimize chrome", "hide the window", "minimize discord"
        ],
        "WHATSAPP_CALL": [
            "call mom", "call Bimal", "can you call John", "make a phone call",
            "call my best friend", "call someone", "ring john", "voice call"
        ],
        "NETWORK_CONTROL": [
            "turn on wifi", "turn off wifi", "disable wi-fi", "enable wi-fi",
            "turn on bluetooth", "turn off bluetooth", "disable bluetooth", "enable bluetooth",
            "toggle wifi", "toggle bluetooth", "turn on bluetooth", "turn on the wi-fi"
        ],
        "BRIGHTNESS_CONTROL": [
            "increase brightness", "decrease brightness", "turn up brightness", "turn down brightness",
            "max brightness", "minimum brightness", "change brightness", "lower brightness",
            "set brightness to", "brightness up", "brightness down", "screen brightness"
        ],
        "VOLUME_CONTROL": [
            "increase volume", "decrease volume", "turn up volume", "turn down volume",
            "mute audio", "unmute", "max volume", "minimum volume", "change volume",
            "lower volume", "set volume to", "volume up", "volume down", "turn it up",
            "make it", "set it to", "decrease it", "increase it"
        ],
        "CONVERSATIONAL_TRAP": [
            "what is my hobby", "who is my favorite artist", "how are you",
            "what is your name", "who am I", "tell me a joke", "search the web",
            "what do i like", "can you answer a question", "hello", "jarvis",
            "play juicewrlds song", "play my favorite artist", "play taylor swift",
            "are you conscious", "do you know who that is", "who is that",
            "what does jarvis mean", "what are you", "how do you work",
            "thank you jarvis now you can shutdown", "now you can shutdown",
            "close that", "what do u see on screen", "what do you see"
        ]
    }

    def __init__(self):
        # 1. Initialize FastTFIDF Primary Router
        self.fast_classifier = FastTFIDF()
        self.fast_classifier.fit(self.INTENTS)
        print("[SemanticRouter] TF-IDF primary router initialized instantly.")

        # 2. Initialize ChromaDB Fallback Router
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
        """Seed the collection with common intent phrases for the fallback router."""
        # Always drop and recreate the collection to ensure new intents are loaded during this upgrade
        try:
            self.client.delete_collection("intents")
        except Exception:
            pass

        self.collection = self.client.get_or_create_collection(
            name="intents",
            embedding_function=self.ef
        )

        docs = []
        ids = []
        metas = []
        idx = 0
        for intent, phrases in self.INTENTS.items():
            for phrase in phrases:
                docs.append(phrase)
                ids.append(f"intent_{idx}")
                metas.append({"intent": intent})
                idx += 1

        print("[SemanticRouter] Seeding intent vectors for ChromaDB fallback...")
        self.collection.add(documents=docs, metadatas=metas, ids=ids)
        print("[SemanticRouter] Fallback intent seeding complete.")

    def route(self, command: str):
        """
        Takes a raw command and returns the matched intent string, or None if unknown.
        It first uses the ultra-fast TF-IDF classifier. If confidence is low, it falls back to ChromaDB.
        """
        try:
            start_t = time.time()
            # 1. Fast Path: TF-IDF
            # Thresholds: ~0.4 is a good balance for TF-IDF cosine similarity.
            fast_intent, fast_score = self.fast_classifier.predict(command, threshold=0.45)

            if fast_intent:
                print(f"[SemanticRouter] Fast-matched '{fast_intent}' with score: {fast_score:.2f} in {(time.time()-start_t)*1000:.1f}ms")
                if fast_intent == "CONVERSATIONAL_TRAP":
                    return None
                return fast_intent

            print(f"[SemanticRouter] TF-IDF failed to find intent (best score: {fast_score:.2f}). Falling back to ChromaDB...")

            # 2. Fallback: ChromaDB
            results = self.collection.query(
                query_texts=[command],
                n_results=1
            )

            if results and results["distances"] and results["distances"][0]:
                distance = results["distances"][0][0]
                intent = results["metadatas"][0][0]["intent"]

                print(f"[SemanticRouter] Fallback matched '{intent}' with distance: {distance:.2f} in {(time.time()-start_t):.2f}s")

                # Dynamic Thresholds for ChromaDB L2 distance
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
