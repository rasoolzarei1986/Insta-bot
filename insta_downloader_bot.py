"""
اسکلت اولیه بات دانلودر اینستاگرام برای تلگرام
"""

import os
import logging
import sqlite3
from datetime import date

import instaloader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
FREE_DAILY_LIMIT = 5  # تعداد دانلود رایگان در روز برای هر کاربر

DB_PATH = "bot_data.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER,
            day TEXT,
            count INTEGER,
            is_premium INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    conn.commit()
    conn.close()


def get_usage(user_id: int):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT count, is_premium FROM usage WHERE user_id=? AND day=?",
        (user_id, today),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], bool(row[1])
    return 0, False


def increment_usage(user_id: int):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO usage (user_id, day, count) VALUES (?, ?, 1)
        ON CONFLICT(user_id, day) DO UPDATE SET count = count + 1
        """,
        (user_id, today),
    )
    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! لینک پست یا ریلز اینستاگرام رو برام بفرست تا دانلودش کنم.\n"
        f"هر کاربر رایگان روزی {FREE_DAILY_LIMIT} دانلود مجاز داره."
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if "instagram.com" not in text:
        await update.message.reply_text("لطفاً یه لینک معتبر اینستاگرام بفرست.")
        return

    count, is_premium = get_usage(user_id)
    if not is_premium and count >= FREE_DAILY_LIMIT:
        await update.message.reply_text(
            "سقف دانلود رایگان امروزت تموم شده. برای دانلود نامحدود /premium رو بزن."
        )
        return

    await update.message.reply_text("در حال دریافت... ⏳")

    try:
        loader = instaloader.Instaloader(
            download_videos=True,
            save_metadata=False,
            download_comments=False,
        )
        shortcode = extract_shortcode(text)
        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        media_url = post.video_url if post.is_video else post.url
        if post.is_video:
            await update.message.reply_video(media_url)
        else:
            await update.message.reply_photo(media_url)

        increment_usage(user_id)

    except Exception as e:
        logger.exception("Download failed")
        await update.message.reply_text(f"دانلود ناموفق بود: {e}")


def extract_shortcode(url: str) -> str:
    parts = [p for p in url.split("/") if p]
    for i, p in enumerate(parts):
        if p in ("p", "reel", "tv") and i + 1 < len(parts):
            return parts[i + 1]
    raise ValueError("shortcode پیدا نشد")


async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "برای دانلود نامحدود می‌تونی از طریق Telegram Stars اشتراک تهیه کنی.\n"
        "(این بخش نیاز به پیاده‌سازی پرداخت داره - سند رسمی: "
        "https://core.telegram.org/bots/payments)"
    )


def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()


if __name__ == "__main__":
    main()
