# Windows Agent (Jarvis)

Jarvis is an ultra-fast, local, autonomous AI Agent for Windows 10/11. Built specifically for systems with limited VRAM (e.g. 4GB), it uses native Windows text-to-speech and `qwen2.5:1.5b` via Ollama for multi-step agentic workflows.

## Demo Video

🎥 Watch the demo:

https://youtu.be/pfRlhW-oROw

## 🚀 Key Features & Full Updates

- **Unified Modular Architecture**: Cleanly separated `client`, `server`, `core`, `agent`, `models`, and `tools` directories for a robust and scalable codebase.
- **Agentic PC Controls**: Maximize, restore, focus, snap windows, hide all windows, and manage system performance.
- **Advanced App Integrations**: Includes powerful WhatsApp audio and video call automation with image recognition fallbacks (`audio_call_btn.png`, `video_call_btn.png`), as well as Spotify playback (`play_btn.png`) and web browsing.
- **Microphone & Streaming STT**: Uses built-in SpeechRecognition (Google STT) with intelligent silence detection, and dynamic PTT (Push-to-Talk) capabilities.
- **Desktop Utilities**: Take screenshots, open shortcut folders, read/write to the clipboard, set timers, and empty the recycle bin via voice commands.
- **Unified Launcher**: Easily start the backend server and desktop client together using the streamlined `run.py` entry point.
- **Model Context Protocol (MCP)**: Now supports MCP integrations.
- **Autonomous Agent**: Uses Ollama with `qwen2.5:1.5b` (default) for intelligent intent routing, file system management, and multi-step tool execution.
- **Memory System**: Remembers user facts and interaction history via a local SQLite database.

## Requirements

- **Python 3.11+** (required)
- Windows 10/11
- [Ollama](https://ollama.ai) installed and running
- Microphone (optional, can use text mode)
- 2GB+ disk space (for models)

## Prerequisites

1. **Install Python 3.11+**
   - Download from https://www.python.org/downloads/
   - Ensure "Add Python to PATH" is checked during installation
   - Verify: `python --version` (should show 3.11 or higher)

2. **Install Ollama**
   - Download from https://ollama.ai
   - Install and ensure it runs as a service
   - Pull the required model: `ollama pull qwen2.5:1.5b`

## Installation

```powershell
# Clone or navigate to the project directory
cd C:\project\assistant

# Create a virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt

# Pull the AI model (if not already done)
# Pull the lightweight agent model
ollama pull qwen2.5:1.5b
```

## Configuration

### Environment Variables (.env file)

Create a `.env` file in the `assistant` folder to customize behavior:

```env
# Server
JARVIS_HOST=0.0.0.0
JARVIS_PORT=8000
JARVIS_BACKEND_URL=http://127.0.0.1:8000

# Model
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_API_URL=http://127.0.0.1:11434/api/generate
OLLAMA_TIMEOUT_SECONDS=60

# Speech Recognition
JARVIS_STT_ENGINE=windows
JARVIS_WAKE_FUZZY_THRESHOLD=0.86

# Visual & TTS Options
JARVIS_HUD=0
JARVIS_SPOKEN_FILLER=0
```

## Running

### Start Ollama (if not running as a service)
```powershell
ollama serve
```

### Run the Assistant
The new unified launcher starts both the FastAPI backend and the client listener:
```powershell
python run.py
```

Alternatively, you can use the `run_assistant.bat` script, which automatically activates your virtual environment and starts the assistant:
```powershell
.\run_assistant.bat
```

**Optional flags:**
- `--no-server` - Run only the client (assumes the server is already running elsewhere).
- `--text` - Run in text mode (no microphone needed, type commands directly).
- `--energy-threshold <int>` - Optional fixed microphone energy threshold.

## Usage

### Voice Commands

Say "Hey Jarvis" to activate, then use commands like:

**Applications & UI Control:**
- "Open Chrome" / "Close Spotify"
- "Maximize window" / "Snap this window to the left"
- "Hide all windows" / "Show desktop"
- "Read my clipboard"

**WhatsApp Integration:**
- "Call [Name] on WhatsApp"
- "Video call [Name] on WhatsApp"

**Desktop Utilities:**
- "Take a screenshot"
- "Empty the recycle bin"
- "Open my downloads folder"
- "Set a timer for 60 seconds"
- "Check system performance"

**Media & System Control:**
- "Play music" / "Next song"
- "Increase volume" / "Mute"
- "Increase brightness" / "Decrease brightness"
- "Shutdown" / "Restart" / "Sleep"

### Text Mode

```powershell
python run.py --text
```
Type commands directly instead of speaking.

## File Structure

```
assistant/
├── run.py                 # Unified launcher for server and client
├── run_assistant.bat      # Helper script to activate venv and run the assistant
├── client/                # Desktop client logic, UI, and audio streaming
├── server/                # FastAPI backend and API routing
├── core/                  # Core configurations and utilities
├── agent/                 # Agentic execution and memory management
├── tools/                 # Extended system tools and capabilities
├── models/                # Local data models
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── jarvis_memory.sqlite3  # Local memory database (auto-created)
```

## Troubleshooting

**Ollama not responding:**
- Ensure Ollama is running: `ollama serve`
- Check port 11434 is accessible

**Microphone not detected:**
- Use text mode: `python run.py --text`
- Check Windows audio settings and PyAudio permissions.

**WhatsApp Automation Issues:**
- Ensure WhatsApp Desktop is installed.
- Ensure `video_call_btn.png` and `audio_call_btn.png` are in the project root if legacy window automation fails.

**Memory not persisting:**
- Check `jarvis_memory.sqlite3` exists and has write permissions.
- Delete file to reset: `del jarvis_memory.sqlite3` (will auto-recreate).

## Important: Data Privacy

Before publishing as open source:
1. Delete `jarvis_memory.sqlite3` (contains personal facts like your name)
2. Ensure `.env` and `__pycache__/` are added to `.gitignore`.

## System Requirements

| Component |       Minimum      |     Recommended    |
|-----------|--------------------|--------------------|
| Python    |      3.11          | 3.12+              |
| RAM       | 4GB                | 8GB+               |
| Disk      | 2GB                | 5GB+               |     
| CPU       | Intel i5 / Ryzen 5 | i7 / Ryzen 7       |
| OS        | Windows 10         | Windows 11         |

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Submit a pull request

## Disclaimer

This project is provided as-is. Use at your own risk. Always review code before executing system commands, especially regarding file deletions or system power options.

