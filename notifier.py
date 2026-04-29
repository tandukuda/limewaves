#!/usr/bin/env python3
"""
notifier.py — watches the mpv IPC socket and fires a desktop
notification via notify-send whenever the track changes.

Run alongside the bot:
    python notifier.py &

Or as a separate systemd user service (limewaves-notifier.service).
"""

import json
import os
import socket
import subprocess
import time
import requests

from config import MPV_SOCKET, NAVIDROME_URL, NAVIDROME_USERNAME, NAVIDROME_PASSWORD
import hashlib, random, string

POLL_INTERVAL = 2  # seconds
COVER_CACHE = "/tmp/limewaves_cover.jpg"


# ------------------------------------------------------------------
# Minimal Subsonic auth to fetch cover art
# ------------------------------------------------------------------

def _cover_url(cover_id: str) -> str:
    salt = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    token = hashlib.md5((NAVIDROME_PASSWORD + salt).encode()).hexdigest()
    params = (
        f"u={NAVIDROME_USERNAME}&t={token}&s={salt}"
        f"&v=1.16.1&c=limewaves-notifier&f=json"
        f"&id={cover_id}&size=200"
    )
    return f"{NAVIDROME_URL}/rest/getCoverArt?{params}"


def fetch_cover(cover_id: str) -> str | None:
    """Download cover art to a temp file and return its path."""
    if not cover_id:
        return None
    try:
        r = requests.get(_cover_url(cover_id), timeout=5)
        r.raise_for_status()
        with open(COVER_CACHE, "wb") as f:
            f.write(r.content)
        return COVER_CACHE
    except Exception:
        return None


# ------------------------------------------------------------------
# mpv IPC helpers
# ------------------------------------------------------------------

def _mpv_get(prop: str):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)
        payload = json.dumps({"command": ["get_property", prop]}) + "\n"
        sock.sendall(payload.encode())
        raw = sock.recv(4096).decode().strip()
        sock.close()
        last = [l for l in raw.splitlines() if l][-1]
        return json.loads(last).get("data")
    except Exception:
        return None


# ------------------------------------------------------------------
# Notification
# ------------------------------------------------------------------

def notify(title: str, artist: str, cover_path: str | None):
    body = artist or "Unknown Artist"
    cmd = ["notify-send", "--app-name=Limewaves", "--urgency=low"]

    if cover_path and os.path.exists(cover_path):
        cmd += [f"--icon={cover_path}"]

    cmd += [title, body]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("notify-send not found. Install libnotify.")
    except subprocess.CalledProcessError as e:
        print(f"notify-send error: {e}")


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------

def main():
    print("👁  Limewaves notifier watching mpv...")
    last_title = None

    while True:
        if not os.path.exists(MPV_SOCKET):
            # mpv not running — reset and wait
            last_title = None
            time.sleep(POLL_INTERVAL)
            continue

        title = _mpv_get("media-title")

        if title and title != last_title:
            last_title = title

            # Try to get richer metadata from mpv metadata map
            artist = _mpv_get("metadata/by-key/artist") or ""

            # Attempt cover art — mpv exposes the stream URL as media-title
            # so we can't get cover_id here directly; we rely on a shared
            # state file written by the bot instead.
            cover_path = COVER_CACHE if os.path.exists(COVER_CACHE) else None

            print(f"🎵 Now playing: {title} — {artist}")
            notify(title, artist, cover_path)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
