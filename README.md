# 🟢 Limewaves

A minimalist, Telegram-controlled music player designed for the ritual of intentional listening.

---

## The Philosophy

I built Limewaves because I have a growing collection of FLAC files purchased directly from artists I love. Supporting artists directly, bypassing streaming services that often underpay them, is important to me. But digital files lack the tactile experience of vinyl or CDs.

With modern digital apps, the default behavior is to skip, shuffle, and build endless playlists. I don't hate those features, but they strip away the experience of listening to an album exactly as the artist intended: from the first track to the last.

Limewaves is not meant to replace Spotify, Navidrome web clients, or full-featured desktop music players. It is built to bring back the ritual. You sit down, pick an album, and let it play. When the album ends, life moves on. It is an intentional, distraction-free environment for pure listening.

---

## The Name

**Limewaves** is a portmanteau of *LimeWire* and *Waves*.

LimeWire shook the industry in the late 90s and early 2000s. While I don't support piracy, that era of P2P technology was the gateway for an entire generation to discover new music. It was a grassroots, cultural moment where people first experienced the freedom of curating their own digital libraries. Limewaves nods to that nostalgic era of owning your files, combined with *Waves* representing the slow, peaceful audio-reactive visuals planned for the project.

---

## How It Works

Limewaves acts as a bridge between your music server and a local playback device, completely bypassing the need for a heavy GUI.

- **Control:** A Telegram bot handles all user inputs (playing albums, queuing, stopping).
- **Backend:** Fetches music directly from a Subsonic-compatible API (Navidrome).
- **Playback:** Routes audio through a headless `mpv` instance controlled via JSON IPC.
- **Visuals:** `projectM` runs as a floating window, reading audio from Pipewire in real-time.

Currently designed to run in a lightweight Linux environment (Hyprland), keeping system resources low and the interface entirely out of the way.

---

## Architecture

```
[Your Phone]
     ↕  Telegram
[Limewaves bot (runs on Omarchy)]
     ↕  Subsonic API (LAN)
[Navidrome]  ←──  [Music storage / NAS]
     ↓  stream URL
[mpv on Omarchy]
     ↓  audio output → Pipewire
[projectM (floating Hyprland window)]
```

---

## Prerequisites

### System packages (Arch / Omarchy)

```bash
sudo pacman -S mpv python projectm libnotify
```

### Python version

Python 3.11+ required.

### Telegram Bot Token

1. Open Telegram → search **@BotFather**
2. `/newbot` → follow prompts → copy the token
3. Get your own user ID from **@userinfobot** (send it `/start`)

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/tandukuda/limewaves.git ~/projects/limewaves
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

| Key | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `ALLOWED_USER_ID` | Your Telegram user ID from @userinfobot |
| `NAVIDROME_URL` | e.g. `http://192.168.1.x:4533` |
| `NAVIDROME_USERNAME` | Your Navidrome login |
| `NAVIDROME_PASSWORD` | Your Navidrome password |
| `MPV_SOCKET` | `/tmp/mpvsocket` (default is fine) |

### 4. Test the Navidrome connection

```bash
source ~/.venv/limewaves/bin/activate
python -c "from navidrome.client import NavidromeClient; print(NavidromeClient().ping())"
# Should print: True
```

---

## Running Limewaves

Limewaves is designed to be run manually, and only when you want to listen.

### Start

```bash
cd ~/projects/limewaves
source ~/.venv/limewaves/bin/activate
python main.py
```

### Start with track change notifications

```bash
cd ~/projects/limewaves
source ~/.venv/limewaves/bin/activate
python notifier.py &
python main.py
```

### Stop

`Ctrl+C` in the terminal. The notifier stops automatically since it shares the same session.

### Optional: shell aliases

Add to your `~/.bashrc` for convenience:

```bash
alias lw="cd ~/projects/limewaves && source ~/.venv/limewaves/bin/activate && python main.py"
alias lw-notify="cd ~/projects/limewaves && source ~/.venv/limewaves/bin/activate && python notifier.py & python main.py"
```

---

## Bot Commands

### Playback

| Command | Description |
|---------|-------------|
| `/play <query>` | Search and immediately play the first result |
| `/queue <query>` | Search and append to queue |
| `/random` | Play 25 random songs |
| `/random <genre>` | Play 25 random songs from a genre |
| `/search <query>` | Browse results as tappable buttons |

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

projectM reads audio from Pipewire automatically, so no extra config is needed as long as mpv is routing through Pipewire (it does by default on Arch).

### Launch projectM

```bash
projectM
```

On Hyprland, make it a floating window by adding to your `hyprland.conf`:

```
windowrulev2 = float, class:^(projectM)$
windowrulev2 = size 800 600, class:^(projectM)$
windowrulev2 = move 100 100, class:^(projectM)$
```

### Preset navigation

- `R`: random preset
- `L`: lock current preset
- `Arrow keys`: browse presets

Presets are stored in `/usr/share/projectM/presets/`. The Milkdrop ones under `presets_milkdrop/` are the most visually interesting.

---

## Project Structure

```
limewaves/
├── main.py                      # Entry point, registers all handlers
├── notifier.py                  # Track change notifier (notify-send)
├── config.py                    # Loads .env into constants
├── requirements.txt
├── .env.example
├── limewaves.service            # systemd user service (optional)
├── limewaves-notifier.service   # systemd user service for notifier (optional)
│
├── navidrome/
│   ├── __init__.py
│   └── client.py                # Subsonic API wrapper (NavidromeClient)
│
├── player/
│   ├── __init__.py
│   └── mpv.py                   # mpv IPC socket controller (MPVController)
│
└── bot/
    ├── __init__.py
    ├── state.py                 # Shared singletons (navidrome, mpv, current_track)
    └── handlers.py              # Telegram command and callback handlers
```

---

## Roadmap

**Phase 1: The Foundation (Current)**
- [x] Telegram bot integration
- [x] Subsonic/Navidrome API connection
- [x] Headless `mpv` playback via IPC socket
- [x] Track change notifications via `notify-send`

**Phase 2: The Visuals**
- [ ] Develop a slow-moving, peaceful custom visualizer using p5.js
- [ ] Extract a color palette from the current track's album art to drive ambient gradient visuals
- [ ] WebSocket bridge for real-time audio analysis → visual parameters

**Phase 3: Dedicated Hardware (The Ritual Setup)**
- [ ] Migrate the player to a dedicated local node (mini PC)
- [ ] Integrate a dedicated DAC/Amp for high-fidelity audio output
- [ ] Connect to a projector to display the ambient visuals in the listening room

---

## Troubleshooting

**Bot doesn't respond**
Check the terminal output for errors. Confirm the token is correct in `.env` and the bot isn't already running in another terminal.

**mpv doesn't start**
Make sure `mpv` is installed: `which mpv`. Check the socket path in `.env` is writable.

**Navidrome ping returns False**
Confirm the URL is reachable: `curl http://192.168.x.x:4533/rest/ping`. Check your credentials in `.env`.

**No audio from projectM**
Run `pactl list sources` and confirm Pipewire is active. projectM should pick up the monitor source automatically.

**No notifications appearing**
Make sure `libnotify` is installed: `sudo pacman -S libnotify`. Run `notify-send test` to confirm it works.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
