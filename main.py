"""
Limewaves — Telegram bot for controlling Navidrome via mpv.
Entry point: python main.py
"""

import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config import TELEGRAM_BOT_TOKEN
from bot import (
    cmd_start, cmd_ping, cmd_search, cmd_play, cmd_queue,
    cmd_random, cmd_np, cmd_pause, cmd_resume, cmd_skip,
    cmd_prev, cmd_stop, cmd_vol, cmd_seek, cmd_genres,
    on_button,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    handlers = [
        ("start",   cmd_start),
        ("ping",    cmd_ping),
        ("search",  cmd_search),
        ("play",    cmd_play),
        ("queue",   cmd_queue),
        ("random",  cmd_random),
        ("np",      cmd_np),
        ("pause",   cmd_pause),
        ("resume",  cmd_resume),
        ("skip",    cmd_skip),
        ("prev",    cmd_prev),
        ("stop",    cmd_stop),
        ("vol",     cmd_vol),
        ("seek",    cmd_seek),
        ("genres",  cmd_genres),
    ]

    for command, handler in handlers:
        app.add_handler(CommandHandler(command, handler))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(on_button))

    logger.info("🟢 Limewaves is running — waiting for commands...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
