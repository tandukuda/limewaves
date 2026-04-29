import json
import os
import socket
import subprocess
import time

from config import MPV_SOCKET


class MPVController:
    """
    Controls mpv via its JSON IPC socket.
    mpv must be started with --input-ipc-server=<MPV_SOCKET>.
    This class spawns mpv automatically on first play if it isn't running.
    """

    def __init__(self):
        self.socket_path = MPV_SOCKET
        self._process = None

    # ------------------------------------------------------------------
    # Socket communication
    # ------------------------------------------------------------------

    def _send(self, command: list):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(self.socket_path)
            payload = json.dumps({"command": command}) + "\n"
            sock.sendall(payload.encode())
            raw = sock.recv(4096).decode().strip()
            sock.close()
            # mpv may send multiple newline-separated JSON objects; take the last
            last_line = [l for l in raw.splitlines() if l][-1]
            return json.loads(last_line)
        except Exception as e:
            return {"error": str(e)}

    def _get(self, prop: str):
        result = self._send(["get_property", prop])
        return result.get("data")

    def _set(self, prop: str, value):
        self._send(["set_property", prop, value])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        return os.path.exists(self.socket_path)

    def _spawn(self, url: str):
        """Start a new mpv process with IPC socket and audio-only mode."""
        cmd = [
            "mpv",
            f"--input-ipc-server={self.socket_path}",
            "--no-video",
            "--really-quiet",
            "--idle=yes",          # keep process alive between tracks
            f"--volume={self._get('volume') or 80}",
            url,
        ]
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # Wait until the socket is ready
        for _ in range(20):
            if self.is_running():
                break
            time.sleep(0.2)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self, url: str):
        """Play a URL immediately, replacing the current track."""
        if not self.is_running():
            self._spawn(url)
        else:
            self._send(["loadfile", url, "replace"])

    def queue(self, url: str):
        """Append a URL to the playlist."""
        if not self.is_running():
            self._spawn(url)
        else:
            self._send(["loadfile", url, "append-play"])

    def pause(self):
        self._set("pause", True)

    def resume(self):
        self._set("pause", False)

    def toggle_pause(self):
        self._send(["cycle", "pause"])

    def stop(self):
        self._send(["stop"])

    def next(self):
        self._send(["playlist-next"])

    def previous(self):
        self._send(["playlist-prev"])

    def seek(self, seconds: int):
        """Seek relative (+ forward, - backward)."""
        self._send(["seek", seconds, "relative"])

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def get_volume(self) -> int | None:
        v = self._get("volume")
        return int(v) if v is not None else None

    def set_volume(self, volume: int):
        volume = max(0, min(100, volume))
        self._set("volume", volume)

    def volume_up(self, step: int = 5):
        self._send(["add", "volume", step])

    def volume_down(self, step: int = 5):
        self._send(["add", "volume", -step])

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_paused(self) -> bool:
        return bool(self._get("pause"))

    def get_title(self) -> str | None:
        return self._get("media-title")

    def get_position(self) -> float | None:
        return self._get("time-pos")

    def get_duration(self) -> float | None:
        return self._get("duration")

    def get_playlist(self) -> list:
        return self._get("playlist") or []

    def get_playlist_pos(self) -> int | None:
        return self._get("playlist-pos")
