"""
Telegram command and callback handlers for Limewaves.
"""

import asyncio
import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.state import current_track, mpv, navidrome
from config import ALLOWED_USER_ID

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Auth guard
# ------------------------------------------------------------------


def _allowed(user_id: int) -> bool:
    return ALLOWED_USER_ID == 0 or user_id == ALLOWED_USER_ID


# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------


def _fmt_time(seconds) -> str:
    if seconds is None:
        return "--:--"
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _track_line(song: dict) -> str:
    return f"🎵 {song.get('title', '?')} — {song.get('artist', 'Unknown')}"


# ------------------------------------------------------------------
# Track state helper
# ------------------------------------------------------------------


async def _cache_track(song: dict):
    # Update in-memory now-playing info (fast, synchronous dict ops)
    current_track.clear()
    current_track.update(
        {
            "id": song.get("id"),
            "title": song.get("title", "Unknown"),
            "artist": song.get("artist", "Unknown"),
            "album": song.get("album", ""),
            "cover_id": song.get("coverArt", ""),
        }
    )

    # Fetch and write cover art off the event loop to avoid blocking
    cover_id = song.get("coverArt")
    if cover_id:
        try:
            art = await asyncio.to_thread(navidrome.get_cover_art_bytes, cover_id, 200)

            def _write(path, data):
                with open(path, "wb") as f:
                    f.write(data)

            await asyncio.to_thread(_write, "/tmp/limewaves_cover.jpg", art)
        except Exception:
            # Best-effort; do not crash the caller
            pass


# ------------------------------------------------------------------
# /start
# ------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    text = (
        "🟢 *Limewaves* — your self-hosted music bot\n\n"
        "*Playback*\n"
        "`/play <query>` — search and play immediately\n"
        "`/queue <query>` — add to queue\n"
        "`/random` — 25 random songs\n"
        "`/random <genre>` — random by genre\n\n"
        "*Controls*\n"
        "`/pause` · `/resume` · `/skip` · `/prev` · `/stop`\n"
        "`/vol <0-100>` — set volume\n"
        "`/seek <±sec>` — seek forward/backward\n\n"
        "*Info*\n"
        "`/np` — now playing + album art\n"
        "`/search <query>` — browse results\n"
        "`/genres` — list genres\n"
        "`/ping` — check Navidrome connection"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ------------------------------------------------------------------
# /ping
# ------------------------------------------------------------------


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    ok = await asyncio.to_thread(navidrome.ping)
    await update.message.reply_text(
        "✅ Navidrome is reachable." if ok else "❌ Cannot reach Navidrome."
    )


# ------------------------------------------------------------------
# /search  — shows inline keyboard, user taps to play
# ------------------------------------------------------------------


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/search <query>`", parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching *{query}*…", parse_mode="Markdown")

    results = await asyncio.to_thread(navidrome.search, query, 8)
    songs = results.get("song", [])

    if not songs:
        await update.message.reply_text("No tracks found.")
        return

    keyboard = []
    for song in songs:
        # callback_data has a 64-byte hard limit in older TG versions — keep it tight
        data = f"play|{song['id']}"
        keyboard.append([InlineKeyboardButton(_track_line(song), callback_data=data)])

    # Store song metadata in context.bot_data keyed by id so the callback can fetch it
    for song in songs:
        context.bot_data[f"song_{song['id']}"] = song

    await update.message.reply_text(
        f"Results for *{query}*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ------------------------------------------------------------------
# /play  — search and immediately start playing first result
# ------------------------------------------------------------------


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: `/play <query>`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    results = await asyncio.to_thread(navidrome.search, query, 1)
    songs = results.get("song", [])

    if not songs:
        await update.message.reply_text("No tracks found.")
        return

    song = songs[0]
    url = await asyncio.to_thread(navidrome.get_stream_url, song["id"])
    await asyncio.to_thread(mpv.play, url)
    await _cache_track(song)

    await update.message.reply_text(
        f"▶️ *{song['title']}*\n👤 {song.get('artist', 'Unknown')}\n💿 {song.get('album', '')}",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------------
# /queue  — search and append to queue
# ------------------------------------------------------------------


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/queue <query>`", parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    results = await asyncio.to_thread(navidrome.search, query, 1)
    songs = results.get("song", [])

    if not songs:
        await update.message.reply_text("No tracks found.")
        return

    song = songs[0]
    url = await asyncio.to_thread(navidrome.get_stream_url, song["id"])
    await asyncio.to_thread(mpv.queue, url)

    await update.message.reply_text(
        f"➕ Queued: *{song['title']}* — {song.get('artist', 'Unknown')}",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------------
# /random
# ------------------------------------------------------------------


async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    genre = " ".join(context.args) if context.args else None
    label = f" *{genre}*" if genre else ""

    songs = await asyncio.to_thread(navidrome.get_random_songs, 25, genre)
    if not songs:
        await update.message.reply_text("No songs found.")
        return

    first, rest = songs[0], songs[1:]
    first_url = await asyncio.to_thread(navidrome.get_stream_url, first["id"])
    await asyncio.to_thread(mpv.play, first_url)
    await _cache_track(first)

    # Fetch stream URLs concurrently to speed up network-bound calls
    urls = await asyncio.gather(
        *(asyncio.to_thread(navidrome.get_stream_url, s["id"]) for s in rest)
    )
    # Queue tracks sequentially to preserve playlist order and avoid concurrent mpv IPC
    for url in urls:
        await asyncio.to_thread(mpv.queue, url)

    await update.message.reply_text(
        f"🎲 Playing random{label}\n\n"
        f"▶️ *{first['title']}*\n👤 {first.get('artist', 'Unknown')}\n"
        f"📋 {len(rest)} more tracks queued",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------------
# /np  — now playing
# ------------------------------------------------------------------


async def cmd_np(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return

    if not await asyncio.to_thread(mpv.is_running):
        await update.message.reply_text("Nothing is playing right now.")
        return

    title = (
        current_track.get("title")
        or await asyncio.to_thread(mpv.get_title)
        or "Unknown"
    )
    artist = current_track.get("artist", "Unknown")
    album = current_track.get("album", "")
    paused = await asyncio.to_thread(mpv.is_paused)
    volume = await asyncio.to_thread(mpv.get_volume)
    pos = await asyncio.to_thread(mpv.get_position)
    dur = await asyncio.to_thread(mpv.get_duration)

    status = "⏸ Paused" if paused else "▶️ Playing"
    text = (
        f"{status}\n\n"
        f"🎵 *{title}*\n"
        f"👤 {artist}\n"
        f"💿 {album}\n"
        f"⏱ {_fmt_time(pos)} / {_fmt_time(dur)}\n"
        f"🔊 {volume}%"
    )

    cover_id = current_track.get("cover_id")
    if cover_id:
        try:
            art = await asyncio.to_thread(navidrome.get_cover_art_bytes, cover_id)
            await update.message.reply_photo(
                photo=io.BytesIO(art), caption=text, parse_mode="Markdown"
            )
            return
        except Exception as e:
            logger.warning("Cover art fetch failed: %s", e)

    await update.message.reply_text(text, parse_mode="Markdown")


# ------------------------------------------------------------------
# Simple controls
# ------------------------------------------------------------------


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    await asyncio.to_thread(mpv.pause)
    await update.message.reply_text("⏸ Paused")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    await asyncio.to_thread(mpv.resume)
    await update.message.reply_text("▶️ Resumed")


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    await asyncio.to_thread(mpv.next)
    await update.message.reply_text("⏭ Skipped")


async def cmd_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    await asyncio.to_thread(mpv.previous)
    await update.message.reply_text("⏮ Previous")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    await asyncio.to_thread(mpv.stop)
    current_track.clear()
    await update.message.reply_text("⏹ Stopped")


async def cmd_vol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        vol = await asyncio.to_thread(mpv.get_volume)
        await update.message.reply_text(f"🔊 Volume: {vol}%")
        return
    try:
        await asyncio.to_thread(mpv.set_volume, int(context.args[0]))
        await update.message.reply_text(f"🔊 Volume set to {context.args[0]}%")
    except ValueError:
        await update.message.reply_text("Usage: `/vol <0-100>`", parse_mode="Markdown")


async def cmd_seek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/seek <seconds>` e.g. `/seek 30` or `/seek -15`",
            parse_mode="Markdown",
        )
        return
    try:
        secs = int(context.args[0])
        await asyncio.to_thread(mpv.seek, secs)
        direction = "⏩" if secs >= 0 else "⏪"
        await update.message.reply_text(
            f"{direction} Seeked {abs(secs)}s {'forward' if secs >= 0 else 'backward'}"
        )
    except ValueError:
        await update.message.reply_text("Seconds must be a number.")


# ------------------------------------------------------------------
# /genres
# ------------------------------------------------------------------


async def cmd_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    genres = await asyncio.to_thread(navidrome.get_genres)
    if not genres:
        await update.message.reply_text("No genres found.")
        return
    lines = "\n".join(
        f"• {g['value']} ({g.get('songCount', 0)} songs)"
        for g in sorted(genres, key=lambda x: -x.get("songCount", 0))[:20]
    )
    await update.message.reply_text(f"🎸 *Genres:*\n\n{lines}", parse_mode="Markdown")


# ------------------------------------------------------------------
# Inline keyboard callback
# ------------------------------------------------------------------


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not _allowed(query.from_user.id):
        return

    data = query.data
    if data.startswith("play|"):
        song_id = data.split("|", 1)[1]
        song = context.bot_data.get(f"song_{song_id}")

        # Fallback: fetch from Navidrome if not cached
        if not song:
            try:
                song = await asyncio.to_thread(navidrome.get_song, song_id)
            except Exception:
                await query.edit_message_text("❌ Could not fetch song info.")
                return

        url = await asyncio.to_thread(navidrome.get_stream_url, song_id)
        await asyncio.to_thread(mpv.play, url)
        await _cache_track(song)

        await query.edit_message_text(
            f"▶️ *{song.get('title', '?')}*\n👤 {song.get('artist', 'Unknown')}\n💿 {song.get('album', '')}",
            parse_mode="Markdown",
        )
