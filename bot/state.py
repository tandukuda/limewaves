"""
Shared singletons — imported by handlers so they all
operate on the same client and player instance.
"""

from navidrome.client import NavidromeClient
from player.mpv import MPVController

navidrome = NavidromeClient()
mpv = MPVController()

# Lightweight now-playing cache updated on every play action.
# Keys: id, title, artist, album, cover_id
current_track: dict = {}
