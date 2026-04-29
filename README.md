# 🟢 Limewaves

> Named after LimeWire — the app that started it all — and waves, for the audio and visuals.

A lightweight Telegram bot that controls music playback from your **Navidrome** server through **mpv** on your local machine, with **projectM** as the visualizer layer.

---

## Architecture

```
[Your Phone]
     ↕  Telegram
[Limewaves bot — runs on Omarchy]
     ↕  Subsonic API (LAN)
[Navidrome on M910Q]  ←──  [Music files on Pi NAS]
     ↓  stream URL
[mpv on Omarchy]
     ↓  audio output
[projectM — floating Hyprland window]
```

---

## Prerequisites

### System packages (Arch / Omarchy)

```bash
sudo pacman -S mpv python projectm
```

### Python version

Python 3.11+ required (uses `int | None` union types).

### Telegram Bot Token

1. Open Telegram → search **@BotFather**
2. `/newbot` → follow prompts → copy the token
3. Get your own user ID from **@userinfobot** (send it `/start`)

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/limewaves.git ~/projects/limewaves
cd ~/projects/limewaves
```

### 2. Create a virtual environment

```bash
python -m venv ~/.venv/limewaves
source ~/.venv/limewaves/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in:

| Key | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `ALLOWED_USER_ID` | Your Telegram user ID from @userinfobot |
| `NAVIDROME_URL` | e.g. `http://192.168.1.x:4533` |
| `NAVIDROME_USERNAME` | Your Navidrome login |
| `NAVIDROME_PASSWORD` | Your Navidrome password |
| `MPV_SOCKET` | `/tmp/mpvsocket` (default is fine) |

### 4. Test the connection first

```bash
source ~/.venv/limewaves/bin/activate
python -c "from navidrome.client import NavidromeClient; print(NavidromeClient().ping())"
# Should print: True
```

### 5. Run the bot

```bash
python main.py
```

Open Telegram → your bot → `/start`

---

## Bot Commands

### Playback

| Command | Description |
|---------|-------------|
| `/play <query>` | Search and immediately play the first result |
| `/queue <query>` | Search and append to queue |
| `/random` | Play 25 random songs |
| `/random <genre>` | Play 25 random songs from a genre |
| `/search <query>` | Show results as tappable buttons |

### Controls

| Command | Description |
|---------|-------------|
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Next track |
| `/prev` | Previous track |
| `/stop` | Stop and clear queue |
| `/vol <0-100>` | Set volume |
| `/vol` | Show current volume |
| `/seek <sec>` | Seek e.g. `/seek 30` or `/seek -15` |

### Info

| Command | Description |
|---------|-------------|
| `/np` | Now playing with album art |
| `/genres` | List genres sorted by song count |
| `/ping` | Test Navidrome connection |

---

## projectM Setup

projectM reads audio from Pipewire automatically — no extra config needed as long as mpv is routing through Pipewire (it does by default on Arch).

### Launch projectM

```bash
projectM-pulseaudio   # or just: projectM
```

On Hyprland, make it a floating window by adding to your `hyprland.conf`:

```
windowrulev2 = float, class:^(projectM)$
windowrulev2 = size 800 600, class:^(projectM)$
windowrulev2 = move 100 100, class:^(projectM)$
```

### Preset navigation

- `R` — random preset
- `L` — lock current preset
- `Arrow keys` — browse presets

Presets are stored in `/usr/share/projectM/presets/`. The Milkdrop ones under `presets_milkdrop/` are the most visually interesting.

---

## Running as a systemd user service

So the bot starts automatically and runs in the background:

```bash
# Copy the service file
mkdir -p ~/.config/systemd/user
cp limewaves.service ~/.config/systemd/user/

# Edit paths if your project is not at ~/projects/limewaves
nano ~/.config/systemd/user/limewaves.service

# Enable and start
systemctl --user daemon-reload
systemctl --user enable limewaves
systemctl --user start limewaves

# Check status
systemctl --user status limewaves

# View logs
journalctl --user -u limewaves -f
```

---

## Project Structure

```
limewaves/
├── main.py                  # Entry point, registers all handlers
├── config.py                # Loads .env into constants
├── requirements.txt
├── .env.example
├── limewaves.service        # systemd user service
│
├── navidrome/
│   ├── __init__.py
│   └── client.py            # Subsonic API wrapper (NavidromeClient)
│
├── player/
│   ├── __init__.py
│   └── mpv.py               # mpv IPC socket controller (MPVController)
│
└── bot/
    ├── __init__.py
    ├── state.py             # Shared singletons (navidrome, mpv, current_track)
    └── handlers.py          # All Telegram command and callback handlers
```

---

## Roadmap

- [x] Phase 1 — Core bot + mpv + projectM on Omarchy laptop
- [ ] Phase 2 — Custom p5.js visualizer with WebSocket audio bridge
- [ ] Phase 3 — Migrate to mini PC, connect DAC + speakers + projector

---

## Troubleshooting

**Bot doesn't respond**
Check `journalctl --user -u limewaves -f` for errors. Confirm the token is correct and the bot isn't already running elsewhere.

**mpv doesn't start**
Make sure `mpv` is installed: `which mpv`. Check the socket path in `.env` is writable.

**Navidrome ping returns False**
Confirm the URL is reachable from the laptop: `curl http://192.168.x.x:4533/rest/ping?u=...`. Check your Navidrome credentials.

**No audio from projectM**
Run `pactl list sources` and confirm Pipewire is active. projectM should pick up the monitor source automatically.

---

## Why the name?

LimeWire was the first place music felt free — even if it technically wasn't. Limewaves is the grown-up, self-hosted version of that same spirit: owning your music experience completely.
