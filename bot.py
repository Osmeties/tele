"""
Telegram Gate Bot - Secure Version
====================================
Keamanan:
- Token & config dari .env (tidak hardcoded)
- Rate limiting per user
- Logging lengkap
- Error handling spesifik
- Admin-only commands
- Input validation
"""

import os
import logging
import time
from collections import defaultdict
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import Forbidden, BadRequest, TelegramError

# ============================================================
# LOAD ENV
# ============================================================
load_dotenv()

TOKEN    = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise EnvironmentError("❌ BOT_TOKEN tidak ditemukan di .env!")
if GROUP_ID == 0:
    raise EnvironmentError("❌ GROUP_ID tidak ditemukan di .env!")

# ============================================================
# CHANNELS — bisa juga dipindah ke .env kalau mau lebih aman
# ============================================================
CHANNELS: dict[str, str] = {
    "Indo 🎬":    os.getenv("CH_INDO",   "https://t.me/+LjRDcKqEWfZkMTMx"),
    "Japan 🎌":   os.getenv("CH_JAPAN",  "https://t.me/+eff65E8r95UwODNh"),
    "Random 🎲":  os.getenv("CH_RANDOM", "https://t.me/+miONvlZdS2U4ZTVh"),
    "Cosplay 👗": os.getenv("CH_COSPLAY","https://t.me/+HBACj3RPsiFhZWE5"),
}

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# RATE LIMITER  (max 5 request per 60 detik per user)
# ============================================================
RATE_LIMIT   = 5
RATE_WINDOW  = 60  # detik
_rate_store: dict[int, list[float]] = defaultdict(list)

def is_rate_limited(user_id: int) -> bool:
    now      = time.time()
    history  = _rate_store[user_id]
    # buang timestamp yang sudah lewat window
    history[:] = [t for t in history if now - t < RATE_WINDOW]
    if len(history) >= RATE_LIMIT:
        return True
    history.append(now)
    return False

# ============================================================
# HELPER — cek apakah user adalah admin bot
# ============================================================
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("/start dari user %s (%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await update.message.reply_text("⏳ Terlalu banyak permintaan. Coba lagi nanti.")
        return

    keyboard = [
        [InlineKeyboardButton("📌 Join Grup", url="https://t.me/+5uw96pDwyzphMjhh")],
        [InlineKeyboardButton("✅ Cek Akses", callback_data="check")],
    ]
    await update.message.reply_text(
        "⚠️ Kamu harus join grup dulu sebelum akses channel!\n\nKlik tombol di bawah:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ============================================================
# Callback: cek keanggotaan grup
# ============================================================
async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    user    = query.from_user
    await query.answer()

    logger.info("Cek akses dari user %s (%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await query.answer("⏳ Terlalu sering. Tunggu sebentar.", show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)

        if member.status in ("member", "administrator", "creator"):
            logger.info("Akses DIBERIKAN ke user %s", user.id)
            keyboard = [
                [InlineKeyboardButton(name, url=link)]
                for name, link in CHANNELS.items()
            ]
            await query.edit_message_text(
                "✅ Akses diberikan! Pilih channel:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            logger.info("Akses DITOLAK untuk user %s (status: %s)", user.id, member.status)
            await query.answer("❌ Kamu belum join grup!", show_alert=True)

    except Forbidden:
        logger.warning("Bot tidak punya izin cek member di grup %s", GROUP_ID)
        await query.answer(
            "⚠️ Bot bukan admin grup. Hubungi admin bot.", show_alert=True
        )
    except BadRequest as e:
        logger.error("BadRequest saat cek member: %s", e)
        await query.answer("⚠️ Gagal memverifikasi. Coba lagi.", show_alert=True)
    except TelegramError as e:
        logger.error("TelegramError: %s", e)
        await query.answer("⚠️ Error Telegram. Coba lagi.", show_alert=True)

# ============================================================
# /id  — hanya admin
# ============================================================
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        logger.warning("Akses /id ditolak untuk user %s", user.id)
        return  # diam saja, tidak kasih tahu

    chat = update.effective_chat
    await update.message.reply_text(
        f"👤 User ID kamu : `{user.id}`\n"
        f"💬 Chat ID sekarang: `{chat.id}`",
        parse_mode="Markdown",
    )
    logger.info("Admin %s minta info ID di chat %s", user.id, chat.id)

# ============================================================
# /status  — hanya admin, cek koneksi bot ke grup
# ============================================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        return

    try:
        chat = await context.bot.get_chat(GROUP_ID)
        me   = await context.bot.get_chat_member(GROUP_ID, context.bot.id)
        await update.message.reply_text(
            f"✅ Bot terhubung ke grup:\n"
            f"📌 Nama  : {chat.title}\n"
            f"🆔 ID    : `{chat.id}`\n"
            f"🤖 Status bot: `{me.status}`",
            parse_mode="Markdown",
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal cek grup: {e}")

# ============================================================
# Error handler global
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception saat handle update:", exc_info=context.error)

# ============================================================
# MAIN
# ============================================================
def main() -> None:
    logger.info("🚀 Bot dimulai...")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("id",     get_id))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(check_access, pattern="^check$"))
    app.add_error_handler(error_handler)

    logger.info("Bot berjalan, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
