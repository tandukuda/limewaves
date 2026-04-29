"""
Telegram command and callback handlers for Limewaves.
"""

import io
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from bot.state import navidrome, mpv, current_track

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

def _cache_track(song: dict):
    current_track.clear()
    current_track.update({
        "id": song.get("id"),
        "title": song.get("title", "Unknown"),
        "artist": song.get("artist", "Unknown"),
        "album": song.get("album", ""),
        "cover_id": song.get("coverArt", ""),
    })


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
    ok = navidrome.ping()
    await update.message.reply_text("✅ Navidrome is reachable." if ok else "❌ Cannot reach Navidrome.")


# ------------------------------------------------------------------
# /search  — shows inline keyboard, user taps to play
# ------------------------------------------------------------------

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: `/search <query>`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching *{query}*…", parse_mode="Markdown")

    results = navidrome.search(query, song_count=8)
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
    results = navidrome.search(query, song_count=1)
    songs = results.get("song", [])

    if not songs:
        await update.message.reply_text("No tracks found.")
        return

    song = songs[0]
    url = navidrome.get_stream_url(song["id"])
    mpv.play(url)
    _cache_track(song)

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
        await update.message.reply_text("Usage: `/queue <query>`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    results = navidrome.search(query, song_count=1)
    songs = results.get("song", [])

    if not songs:
        await update.message.reply_text("No tracks found.")
        return

    song = songs[0]
    url = navidrome.get_stream_url(song["id"])
    mpv.queue(url)

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

    songs = navidrome.get_random_songs(size=25, genre=genre)
    if not songs:
        await update.message.reply_text("No songs found.")
        return

    first, rest = songs[0], songs[1:]
    mpv.play(navidrome.get_stream_url(first["id"]))
    _cache_track(first)

    for s in rest:
        mpv.queue(navidrome.get_stream_url(s["id"]))

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

    if not mpv.is_running():
        await update.message.reply_text("Nothing is playing right now.")
        return

    title = current_track.get("title") or mpv.get_title() or "Unknown"
    artist = current_track.get("artist", "Unknown")
    album = current_track.get("album", "")
    paused = mpv.is_paused()
    volume = mpv.get_volume()
    pos = mpv.get_position()
    dur = mpv.get_duration()

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
            art = navidrome.get_cover_art_bytes(cover_id)
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
    mpv.pause()
    await update.message.reply_text("⏸ Paused")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    mpv.resume()
    await update.message.reply_text("▶️ Resumed")


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    mpv.next()
    await update.message.reply_text("⏭ Skipped")


async def cmd_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    mpv.previous()
    await update.message.reply_text("⏮ Previous")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    mpv.stop()
    current_track.clear()
    await update.message.reply_text("⏹ Stopped")


async def cmd_vol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        vol = mpv.get_volume()
        await update.message.reply_text(f"🔊 Volume: {vol}%")
        return
    try:
        mpv.set_volume(int(context.args[0]))
        await update.message.reply_text(f"🔊 Volume set to {context.args[0]}%")
    except ValueError:
        await update.message.reply_text("Usage: `/vol <0-100>`", parse_mode="Markdown")


async def cmd_seek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: `/seek <seconds>` e.g. `/seek 30` or `/seek -15`", parse_mode="Markdown")
        return
    try:
        secs = int(context.args[0])
        mpv.seek(secs)
        direction = "⏩" if secs >= 0 else "⏪"
        await update.message.reply_text(f"{direction} Seeked {abs(secs)}s {'forward' if secs >= 0 else 'backward'}")
    except ValueError:
        await update.message.reply_text("Seconds must be a number.")


# ------------------------------------------------------------------
# /genres
# ------------------------------------------------------------------

async def cmd_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    genres = navidrome.get_genres()
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
                song = navidrome.get_song(song_id)
            except Exception:
                await query.edit_message_text("❌ Could not fetch song info.")
                return

        url = navidrome.get_stream_url(song_id)
        mpv.play(url)
        _cache_track(song)

        await query.edit_message_text(
            f"▶️ *{song.get('title', '?')}*\n👤 {song.get('artist', 'Unknown')}\n💿 {song.get('album', '')}",
            parse_mode="Markdown",
        )
