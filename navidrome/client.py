import hashlib
import random
import string
import requests
from config import NAVIDROME_URL, NAVIDROME_USERNAME, NAVIDROME_PASSWORD


class NavidromeClient:
    """
    Thin wrapper around the Subsonic API exposed by Navidrome.
    Auth uses the token-based method: md5(password + salt).
    """

    CLIENT_NAME = "limewaves"
    API_VERSION = "1.16.1"

    def __init__(self):
        self.base_url = NAVIDROME_URL
        self.username = NAVIDROME_USERNAME
        self.password = NAVIDROME_PASSWORD

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth(self) -> dict:
        salt = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        token = hashlib.md5((self.password + salt).encode()).hexdigest()
        return {
            "u": self.username,
            "t": token,
            "s": salt,
            "v": self.API_VERSION,
            "c": self.CLIENT_NAME,
            "f": "json",
        }

    def _get(self, endpoint: str, **params):
        url = f"{self.base_url}/rest/{endpoint}"
        response = requests.get(url, params={**self._auth(), **params}, timeout=10)
        response.raise_for_status()
        data = response.json().get("subsonic-response", {})
        if data.get("status") != "ok":
            error = data.get("error", {})
            raise RuntimeError(f"Subsonic error {error.get('code')}: {error.get('message')}")
        return data

    def _stream_url(self, endpoint: str, **params) -> str:
        """Build a direct URL (no JSON, used for streaming/cover art)."""
        from urllib.parse import urlencode
        return f"{self.base_url}/rest/{endpoint}?{urlencode({**self._auth(), **params})}"

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        try:
            self._get("ping")
            return True
        except Exception:
            return False

    def search(self, query: str, song_count: int = 10, album_count: int = 3, artist_count: int = 3) -> dict:
        """Search tracks, albums, and artists."""
        result = self._get(
            "search3",
            query=query,
            songCount=song_count,
            albumCount=album_count,
            artistCount=artist_count,
        )
        return result.get("searchResult3", {})

    def get_random_songs(self, size: int = 25, genre: str = None) -> list:
        params = {"size": size}
        if genre:
            params["genre"] = genre
        result = self._get("getRandomSongs", **params)
        return result.get("randomSongs", {}).get("song", [])

    def get_album(self, album_id: str) -> dict:
        result = self._get("getAlbum", id=album_id)
        return result.get("album", {})

    def get_album_list(self, list_type: str = "newest", size: int = 10) -> list:
        """list_type: newest | frequent | recent | starred | random | alphabeticalByName"""
        result = self._get("getAlbumList2", type=list_type, size=size)
        return result.get("albumList2", {}).get("album", [])

    def get_song(self, song_id: str) -> dict:
        result = self._get("getSong", id=song_id)
        return result.get("song", {})

    def get_genres(self) -> list:
        result = self._get("getGenres")
        return result.get("genres", {}).get("genre", [])

    def get_stream_url(self, song_id: str) -> str:
        return self._stream_url("stream", id=song_id)

    def get_cover_art_url(self, cover_id: str, size: int = 400) -> str:
        return self._stream_url("getCoverArt", id=cover_id, size=size)

    def get_cover_art_bytes(self, cover_id: str, size: int = 400) -> bytes:
        url = self.get_cover_art_url(cover_id, size)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
