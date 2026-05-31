# Windows Assistant (Jarvis)

A voice-activated Windows desktop assistant that listens to commands and performs actions like opening applications, controlling volume/brightness, playing music, and executing system operations.

## Demo Video

🎥 Watch the demo:

https://youtu.be/pfRlhW-oROw

## Features

- 🎤 **Voice Commands** - Wake word recognition ("Hey Jarvis") with speech-to-text
- 🚀 **App Control** - Open, close, and manage Windows applications
- 🔊 **Media Control** - Play/pause, next/previous tracks, volume and brightness control
- 📱 **Smart Integration** -Spotify playback, web browsing
- 💾 **Memory System** - Remembers user facts and interaction history
- 🤖 **AI-Powered** - Uses Ollama with gemma2:2b for intelligent command routing
- 🖥️ **Windows Clients** - Works with Windows desktop (PC)
- ⚙️ **Customizable** - Extensive configuration options via environment variables

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
   - Pull the required model: `ollama pull gemma2:2b`

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
ollama pull gemma2:2b
```

## Configuration

### Environment Variables (.env file)

Create a `.env` file in the `assistant` folder to customize behavior:

```env
# Server
JARVIS_HOST=0.0.0.0
JARVIS_PORT=8000

# Model
OLLAMA_MODEL=gemma2:2b
OLLAMA_API_URL=http://127.0.0.1:11434/api/generate
OLLAMA_TIMEOUT_SECONDS=60

# Memory
JARVIS_MEMORY_HISTORY_LIMIT=12
JARVIS_MEMORY_FACT_LIMIT=20

# Speech Recognition
JARVIS_STT_ENGINE=whisper
JARVIS_WHISPER_MODEL=distil-medium.en
JARVIS_WAKE_FUZZY_THRESHOLD=0.86

# TTS Engine
JARVIS_TTS_ENGINE=pyttsx3
```

## Running

### Start Ollama (if not running as service)
```powershell
ollama serve
```

### Run Backend Server
```powershell
python main.py
```

### Run Desktop Client (in another terminal)
```powershell
python start_assistant.py
```

**Optional flags:**
- `--text` - Run in text mode (no microphone needed)
- `--install-startup` - Install Windows startup launcher
- `--uninstall-startup` - Remove startup launcher

## Usage

### Voice Commands

Say "Hey Jarvis" to activate, then use commands like:

**Applications:**
- "Open Chrome"
- "Close Spotify"
- "Launch VS Code"

**Media:**
- "Play music"
- "Play [song name] on Spotify"
- "Next song" / "Previous song"
- "Pause" / "Play | Resume "

**System Control:**
- "Increase volume" / "Decrease volume" / "Mute"
- "Increase brightness" / "Decrease brightness"
- "Turn on WiFi" / "Turn off Bluetooth"
- "Shutdown" / "Restart" / "Sleep"

**Information:**
- "What's the time?"
- "What's the date?"
- "What's my name?"

### Text Mode

```powershell
python start_assistant.py --text
```

Type commands directly instead of speaking.

## File Structure

```
assistant/
├── main.py                 # Backend API server
├── start_assistant.py      # Desktop client launcher
├── laptop_assistant.py     # Voice/text input handling
├── model.py               # AI model integration (Ollama)
├── memory_store.py        # SQLite memory management
├── pc_controls.py         # Windows system control
├── config.py              # Configuration loading
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── jarvis_memory.sqlite3 # Local memory database (auto-created)
└── contacts.json         # User contacts (optional)
```

## Troubleshooting

**Ollama not responding:**
- Ensure Ollama is running: `ollama serve`
- Check port 11434 is accessible

**Microphone not detected:**
- Use text mode: `python start_assistant.py --text`
- Check Windows audio settings

**Models not downloading:**
- Manually pull: `ollama pull gemma2:2b`
- Ensure internet connection

**Memory not persisting:**
- Check `jarvis_memory.sqlite3` exists and has write permissions
- Delete file to reset: `del jarvis_memory.sqlite3` (will auto-recreate)

## Important: Data Privacy

Before publishing as open source:
1. Delete `jarvis_memory.sqlite3` (contains personal facts like your name)
2. Create `.gitignore` to exclude:
   ```
   jarvis_memory.sqlite3
   .env
   contacts.json
   __pycache__/
   *.pyc
   ```

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

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation

## Disclaimer

This project is provided as-is. Use at your own risk. Always review code before executing system commands.
