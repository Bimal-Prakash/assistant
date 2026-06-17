# Jarvis Assistant - Developer & Architecture Guide

This document provides a comprehensive A-to-Z overview of how the Jarvis Windows Assistant is built, its architectural design, the workflow of requests, the technology stack, and instructions on model switching.

## 1. Project Overview & Architecture

Jarvis is a local, autonomous AI agent built specifically for Windows 10/11. It is designed to operate on consumer hardware with limited VRAM (e.g., 4GB) while offering a rich set of features including voice-to-text, PC management, system controls, and app integrations like WhatsApp and Spotify.

To ensure a robust and scalable codebase, the project uses a **Client-Server Architecture** running locally on the same machine:

- **Unified Launcher (`run.py` / `run_assistant.bat`)**: The entry point that simultaneously starts the backend server and the desktop client in separate threads.
- **Desktop Client (`client/`)**: Handles all user interactions, capturing audio, performing Speech-To-Text (STT), managing the HUD (Heads-Up Display), executing direct PC controls (like adjusting volume or brightness), and rendering Text-To-Speech (TTS) responses.
- **Backend Server (`server/`)**: A FastAPI REST backend that processes complex intents, manages memory, routes requests to the LLM, and delegates tool execution.
- **Agent System (`agent/`)**: The "brain" of the system, taking user queries, interacting with the Ollama API, managing memory states (via SQLite), and utilizing Model Context Protocol (MCP) integrations.
- **Tools (`tools/`)**: A suite of capabilities such as web browsing, image recognition-based UI automation (PyAutoGUI + OpenCV), and system queries.

## 2. The Technology Stack

The project relies entirely on open-source and native Python integrations:

### Core Frameworks
- **Python 3.11+**: The foundational language.
- **FastAPI & Uvicorn**: Powers the high-performance, asynchronous REST API backend.

### Artificial Intelligence & Local LLMs
- **Ollama**: Serves the local LLM inference API (`http://127.0.0.1:11434/api/generate`).
- **qwen2.5:1.5b**: The default lightweight model, chosen specifically for its ultra-fast inference on low-VRAM GPUs.

### Speech & Audio Processing
- **SpeechRecognition**: Core STT wrapper. By default, it uses the built-in Windows STT engine to avoid heavy local processing.
- **pyttsx3 & edge-tts**: Provides low-latency Text-to-Speech playback. 
- **PyAudio**: Streams microphone data.

### System & Desktop Automation
- **PyAutoGUI & OpenCV (`cv2`)**: Handles visual fallback automation (e.g., finding `video_call_btn.png` to click on screen for WhatsApp calls).
- **screen-brightness-control**: Adjusts monitor brightness natively.
- **pycaw & comtypes**: Hooks into Windows Core Audio APIs to control and read exact volume levels.
- **Spotipy**: Connects to Spotify APIs for media playback and management.

### Data Storage & RAG Memory
- **SQLite3**: A local database (`jarvis_memory.sqlite3`) for persistent memory, allowing the agent to remember user facts and interaction history without sending data to the cloud.
- **ChromaDB**: Used for both Semantic Intent Routing (caching voice commands) and Retrieval-Augmented Generation (RAG) by vectorizing personal Obsidian Markdown notes.

### NLP & UI Automation
- **spaCy**: Used for Natural Language Parsing (`en_core_web_sm`) to cleanly extract application names and entities from user speech.
- **UICacheManager**: A Singleton background daemon thread that constantly polls the active window DOM tree using `uiautomation`, dropping UI latency to 0.0s.

## 3. The Execution Workflow (A to Z)

Here is exactly what happens when you say a command:

1. **Wake Word & Capture**: The microphone continuously listens. Using energy thresholds and silence detection, it captures a spoken phrase.
2. **Speech-to-Text (STT)**: The `client/audio/stt_dispatcher.py` transcribes the audio using the configured engine (Windows native by default).
3. **Local Action Evaluation & Semantic Routing**: 
   - The client uses a **Semantic Router Bypass** (ChromaDB) to evaluate if the command is a simple, predictable action (e.g., *"mute volume"*, *"snap this window"*, *"close this"*).
   - The router uses `spaCy` NLP to parse exact entities from the text.
   - If the intent requires context (like *"close this"*), the router instantly queries the background `UICacheManager` to determine the active window.
   - If a fast path is matched, it executes immediately using Windows APIs without ever contacting the LLM (zero-latency).
   - If no fast path is matched, the raw text command is packaged and sent via an HTTP POST request to the FastAPI backend (`http://127.0.0.1:8000`).
4. **Agent Reasoning**: The FastAPI endpoint receives the request and forwards it to `agent/llm.py`. 
5. **Tool Selection & Memory Retrieval**: 
   - The agent reads previous context from SQLite.
   - It prompts the local Ollama LLM with available tools.
   - The LLM decides whether it needs to invoke a tool (like `exec_whatsapp_call` in `tools/executors/whatsapp.py`) or simply respond with text.
6. **Execution & Response**: 
   - If a tool is invoked, the backend executes the tool logic and gathers the result.
   - The backend formulates a final JSON response.
7. **Text-To-Speech (TTS)**: The client receives the JSON, parses the `message` field, and triggers the TTS engine to speak the response aloud to the user.

## 4. Model Switching & Configuration

Jarvis is completely model-agnostic. While it ships with `qwen2.5:1.5b` (for maximum speed on limited hardware), switching models is seamless.

### How Model Selection Works
The agent dynamically reads the model name from the environment variables (`OLLAMA_MODEL`) every time it makes a request to the Ollama endpoint (`http://127.0.0.1:11434/api/generate`). It passes this model name in the JSON payload.

### Step-by-Step Model Switching

**1. Pull the New Model**
Open your terminal and use Ollama to pull your desired model. For example, to switch to the larger and more capable `llama3`:
```powershell
ollama pull llama3
```

**2. Update the Environment Variable**
Open the `.env` file in the root of the project directory. If it doesn't exist, create it. Locate or add the `OLLAMA_MODEL` property:
```env
# Change from qwen2.5:1.5b to llama3
OLLAMA_MODEL=llama3
```

**3. Restart the Assistant**
Simply stop the running instance (Ctrl+C) and restart it using the launcher script:
```powershell
.\run_assistant.bat
```
*(Or run `python run.py`)*

The system will now boot up. The next time the client sends a request to the backend, the `agent/llm.py` file will read `OLLAMA_MODEL=llama3` and instruct Ollama to use the new model for all reasoning and tool selection.

**Recommended Models by Hardware:**
- **4GB VRAM or less**: `qwen2.5:1.5b` or `gemma2:2b`
- **8GB VRAM**: `llama3` or `phi3`
- **12GB+ VRAM**: `llama3:8b` or `mixtral`
