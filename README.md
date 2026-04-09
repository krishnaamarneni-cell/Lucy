cat > ~/Lucy/README.md << 'EOF'
# Lucy 🎙️

A local voice assistant for Windows/WSL. Lucy listens for a wake word, understands speech, and responds using Groq-hosted LLaMA. She remembers facts about you, controls your volume, checks the weather, searches the web, sets reminders, and runs quietly in the background.

## Features

- 🎯 **Wake word detection** — say "Alexa" to activate
- 🎤 **Speech-to-text** via Groq Whisper
- 🧠 **LLaMA 3.1 brain** via Groq
- 💾 **Persistent memory** — remembers your name, preferences, and facts
- 🕐 **Time & date** queries
- 🌤️ **Live weather** lookups
- 🔍 **Web search**
- ⏰ **Reminders**
- 🔊 **Volume control** (via pactl)
- 😴 **Auto-sleep** after inactivity
- 🛑 **Stop command**

## Requirements

- Windows 10/11 with WSL2 (Ubuntu)
- Python 3.10+
- PulseAudio (`pactl`)
- A free [Groq API key](https://console.groq.com)
- A microphone accessible from WSL

## Installation

```bash
git clone https://github.com/krishnaamarneni-cell/Lucy.git ~/Lucy
cd ~/Lucy

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # paste your Groq API key

chmod +x start_lucy.sh
```

## Running Lucy

```bash
./start_lucy.sh start     # Start in the background
./start_lucy.sh stop      # Stop
./start_lucy.sh restart   # Restart
./start_lucy.sh status    # Is she running?
./start_lucy.sh logs      # Tail the log (Ctrl+C to exit)
```

Once running, say **"Alexa"** to wake her, then speak your command.

## Auto-start on WSL launch

Add this to `~/.bashrc` so Lucy starts whenever you open WSL:

```bash
if [[ -z "$LUCY_AUTOSTARTED" ]] && [[ -x "$HOME/Lucy/start_lucy.sh" ]]; then
  export LUCY_AUTOSTARTED=1
  "$HOME/Lucy/start_lucy.sh" start >/dev/null 2>&1 &
fi
```

## Example commands

- "Alexa, what time is it?"
- "Alexa, what's the weather?"
- "Alexa, remember that I love coding at night"
- "Alexa, what do you know about me?"
- "Alexa, turn the volume up"
- "Alexa, remind me to stretch in 15 minutes"
- "Alexa, what's the latest news on AI?"
- "Alexa, stop"

## Project structure