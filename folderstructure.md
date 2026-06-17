# Jarvis Folder Structure

The Jarvis project is organized using a clean Client-Server architecture to decouple the frontend audio/UI capture from the heavy AI backend. 

Here is the fully expanded structure covering every core module and file:

```text
assistant/
│
├── run.py                        # The unified launcher that starts both the backend and client.
├── run_assistant.bat             # Helper script to activate virtual environment and run the assistant.
├── requirements.txt              # Python dependencies needed for the project.
├── .env                          # Configuration environment variables (API keys, ports, models).
├── jarvis_memory.sqlite3         # The local SQLite database for persistent agent memory.
│
├── README.md                     # Main documentation, setup instructions, and feature list.
├── ARCHITECTURE.md               # Detailed technical guide on how the assistant works internally.
├── CONTRIBUTING.md               # Guidelines for open-source community contributions.
├── SECURITY.md                   # Security policies and vulnerability reporting.
└── CODE_OF_CONDUCT.md            # Community code of conduct.
│
├── agent/                        # The "Brain" of the system
│   ├── llm.py                    # The core ReAct reasoning loop that talks to Ollama.
│   ├── mcp_client.py             # Client for handling Model Context Protocol integrations.
│   └── memory/                   # SQLite memory managers and vector database integrations.
│       ├── connection.py         # DB connection setup.
│       ├── extraction.py         # Entity extraction for memory.
│       ├── read.py               # Memory retrieval logic.
│       └── write.py              # Memory persistence logic.
│
├── client/                       # The Desktop Client (Audio, Parsing, and Fast-Path execution)
│   ├── app.py                    # The main client lifecycle and event loop.
│   ├── config.py                 # Client-specific configurations.
│   ├── ui.py                     # The visual Heads-Up Display (HUD) overlay.
│   ├── audio/                    # Speech-To-Text (STT) dispatcher and PyAudio streaming.
│   │   ├── device.py             # OS-level audio device mapping.
│   │   ├── stt_dispatcher.py     # Transcribes microphone input to text.
│   │   └── tts.py                # Text-to-Speech playback (pyttsx3/edge-tts).
│   ├── core/                     # Fast-path Execution Resolvers, Semantic Routers, and Keyboard Hooks.
│   │   ├── aliases.py            # Hardcoded alias resolutions.
│   │   ├── backend.py            # HTTP Client communicating with the FastAPI server.
│   │   ├── confirmation.py       # Handles safety confirmation states (e.g. shutdown).
│   │   ├── execution_actions.py  # Dispatcher for fast-path actions.
│   │   ├── execution_heuristics.py # Intent guessing fallbacks.
│   │   ├── execution_resolver.py # The bypass router matching common commands.
│   │   ├── keyboard.py           # Native keyboard hooks (Push-to-talk).
│   │   ├── main.py               # Client loop core implementation.
│   │   ├── rules.py              # Rule engine for execution overrides.
│   │   ├── semantic_router.py    # Zero-latency ChromaDB Vector router.
│   │   ├── ui_updater.py         # HUD status updates.
│   │   └── window.py             # Basic window management.
│   ├── nlp/                      # spaCy Text Normalization and Entity Extraction.
│   │   ├── calibration.py        # NLP model loader and cache.
│   │   ├── gating.py             # Decision gates for conversational logic.
│   │   ├── normalization.py      # Cleans stutters, repeated words, and synonyms.
│   │   └── wake_word.py          # Fuzzy wake-word ("Hey Jarvis") matching.
│   └── system/                   # Instant execution modules (closing apps, opening files, media control).
│       ├── agentic_core.py       # Multi-threaded deep parallel file search and execution.
│       ├── apps_core.py          # Z-order aware App closer and minimizer (pygetwindow).
│       ├── apps_search.py        # Program Files indexing and matching.
│       ├── apps_spotify.py       # Spotify API integration.
│       └── apps_startup.py       # Handles startup execution rules.
│
├── core/                         # Shared Utilities
│   ├── config.py                 # Global variables shared across client and server.
│   └── prompts.py                # System instructions and prompt templates for the LLM.
│
├── server/                       # The Backend API
│   ├── app.py                    # The FastAPI application entry point.
│   ├── dependencies.py           # Dependency injection for the API routes.
│   ├── api/                      # REST endpoints (e.g., POST /command).
│   │   └── routes.py             # Fast API endpoint definitions.
│   └── parser/                   # Sanitizes and parses raw JSON output from the LLM.
│       ├── contacts.py           # Contact alias parser.
│       ├── media.py              # Media intent parser.
│       ├── normalizer.py         # JSON and string artifact cleaner.
│       └── system.py             # System execution payload parser.
│
└── tools/                        # The Agent's Toolkit (Functions the LLM can call)
    ├── registry.py               # The central registry exposing tool schemas to the LLM.
    ├── dispatch.py               # Routes the LLM's chosen tool to the actual function.
    ├── web.py                    # Web scraping and browser automation utilities.
    ├── executors/                # Specific tool implementations called directly by the LLM.
    │   ├── agentic.py            # Agentic core bindings.
    │   ├── apps.py               # Application interaction execution.
    │   ├── brightness.py         # Monitor brightness controller.
    │   ├── chatgpt.py            # Clipboard-based silent ChatGPT automation.
    │   ├── file_system.py        # File readers, writers, and listers.
    │   ├── final_answer.py       # The terminal conversation action.
    │   ├── media.py              # Spotify/Youtube media execution.
    │   ├── memory.py             # Memory insertion tools.
    │   ├── mic.py                # Microphone interaction overrides.
    │   ├── network.py            # WiFi/Bluetooth execution.
    │   ├── obsidian.py           # RAG-based Obsidian note vector searching.
    │   ├── power.py              # Sleep/Restart/Shutdown execution.
    │   ├── system_info.py        # Retrieves time, date, battery, etc.
    │   ├── terminal.py           # Shell command execution.
    │   ├── ui_automation.py      # OpenCV + PyAutoGUI interactive vision execution.
    │   ├── vision.py             # Moondream visual LLM screencapture execution.
    │   ├── volume.py             # Audio device volume execution.
    │   ├── web_search.py         # DuckDuckGo/Google search hooks.
    │   ├── website.py            # URL Opener.
    │   └── whatsapp.py           # WhatsApp Desktop API automation.
    └── system/                   # Low-level Windows OS calls.
        ├── brightness.py         # WMI screen-brightness-control.
        ├── media.py              # Windows virtual key media hooks.
        ├── mic.py                # Coreaudio microphone interactions.
        ├── network.py            # Windows `netsh` network controls.
        ├── power.py              # `shutdown` and `rundll32` power commands.
        └── volume.py             # Coreaudio volume endpoint.
```

### Key Highlights
- **No Cloud Dependencies:** You'll notice there are no heavy cloud config folders. Everything is designed to run locally on your device using `agent/` and `tools/`.
- **Zero-Latency Design:** The `client/core/` and `client/system/` directories completely bypass the `server/` for basic PC tasks, ensuring instant response times.
