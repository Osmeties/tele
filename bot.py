"""
Telegram Gate Bot - Full Secure Version
========================================
Fitur:
- Token & config dari environment variable (Railway/VPS)
- Rate limiting per user (5 request / 60 detik)
- Menu channel expired otomatis setelah 5 menit
- Welcome message otomatis saat member baru join grup
- Logging lengkap (terminal + file)
- Error handling spesifik
- Admin-only commands (/id, /status)
- Global error handler
"""

import os
import logging
import time
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
)
from telegram.error import Forbidden, BadRequest, TelegramError

# ============================================================
# CONFIG — diambil dari environment variable (Railway dashboard)
# ============================================================
TOKEN    = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise EnvironmentError("❌ BOT_TOKEN tidak ditemukan di environment variable!")
if GROUP_ID == 0:
    raise EnvironmentError("❌ GROUP_ID tidak ditemukan di environment variable!")

# ============================================================
# CHANNELS — diambil dari env, fallback ke link default
# ============================================================
CHANNELS: dict[str, str] = {
    "Indo 🎬":    os.getenv("CH_INDO",    "https://t.me/channel_indo"),
    "Japan 🎌":   os.getenv("CH_JAPAN",   "https://t.me/channel_japan"),
    "Random 🎲":  os.getenv("CH_RANDOM",  "https://t.me/channel_random"),
    "Cosplay 👗": os.getenv("CH_COSPLAY", "https://t.me/channel_cosplay"),
}

# ============================================================
# KONSTANTA
# ============================================================
RATE_LIMIT          = 5    # max request per window
RATE_WINDOW         = 60   # detik
MENU_EXPIRE_SECONDS = 300  # 5 menit

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
# STORAGE
# ============================================================
_rate_store: dict[int, list[float]] = defaultdict(list)
channel_menu_time: dict[int, float] = {}

# ============================================================
# HELPERS
# ============================================================
def is_rate_limited(user_id: int) -> bool:
    """Cek apakah user melebihi batas request."""
    now     = time.time()
    history = _rate_store[user_id]
    history[:] = [t for t in history if now - t < RATE_WINDOW]
    if len(history) >= RATE_LIMIT:
        return True
    history.append(now)
    return False

def is_admin(user_id: int) -> bool:
    """Cek apakah user adalah admin bot."""
    return user_id == ADMIN_ID

def extract_status_change(chat_member_update: ChatMemberUpdated):
    """
    Ambil status lama dan baru dari update ChatMember.
    Return (was_member, is_member) atau None jika tidak relevan.
    """
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status

    was_member = old_status in ("member", "administrator", "creator", "restricted")
    is_member  = new_status in ("member", "administrator", "creator", "restricted")

    return was_member, is_member

# ============================================================
# HANDLER: /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("/start dari user %s (@%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await update.message.reply_text("⏳ Terlalu banyak permintaan. Coba lagi nanti.")
        return

    keyboard = [
        [InlineKeyboardButton("📌 Join Grup", url="https://t.me/+5uw96pDwyzphMjhh")],
        [InlineKeyboardButton("✅ Cek Akses", callback_data="check")],
    ]
    await update.message.reply_text(
        "⚠️ Kamu harus join grup dulu sebelum akses channel!\n\n"
        "Klik tombol di bawah:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ============================================================
# HANDLER: Welcome member baru
# ============================================================
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kirim pesan welcome saat ada member baru join grup."""
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result

    # Hanya proses kalau user BARU join (bukan keluar atau hal lain)
    if was_member or not is_member:
        return

    user = update.chat_member.new_chat_member.user
    chat = update.effective_chat

    logger.info("Member baru join: %s (@%s) di grup %s", user.id, user.username, chat.id)

    # Mention user dengan link profil
    mention = f"[{user.first_name}](tg://user?id={user.id})"

    welcome_text = (
        f"Selamat Datang {mention}\\! 👋\n\n"
        "WELCOME TO WARKOP JAM RAWAN\n"
        "🔥𝗧𝗘𝗠𝗣𝗔𝗧 𝗞𝗛𝗨𝗦𝗨𝗦 𝟭𝟴\\+🔥\n"
        "KONTEN INDO TERUPDATE\\!\\!\n"
        "GRATIS TINGGAL NONTON\n"
        "DISINI👇👇👇\n"
        "/start\n\n"
        "Bisa request video di WJR Group ✔️\n"
        "Update Setiap Hari ✔️\n"
        "GRATIS seumur hidup ✔️"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 Klik /start untuk Akses", url=f"https://t.me/{context.bot.username}?start=welcome")],
    ]

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=welcome_text,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except TelegramError as e:
        logger.error("Gagal kirim welcome message: %s", e)

# ============================================================
# HANDLER: Callback "Cek Akses"
# ============================================================
async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = query.from_user
    await query.answer()

    logger.info("Cek akses dari user %s (@%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await query.answer("⏳ Terlalu sering. Tunggu sebentar.", show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)

        if member.status in ("member", "administrator", "creator"):
            logger.info("✅ Akses DIBERIKAN ke user %s", user.id)

            # Simpan waktu menu dikirim
            channel_menu_time[user.id] = time.time()

            keyboard = [
                [InlineKeyboardButton(name, url=link)]
                for name, link in CHANNELS.items()
            ]
            await query.edit_message_text(
                "✅ Akses diberikan\\! Pilih channel:\n\n"
                "⏳ Menu ini aktif selama *5 menit*\\.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2",
            )

            # Batalkan job lama jika ada
            old_jobs = context.job_queue.get_jobs_by_name(f"expire_{user.id}")
            for job in old_jobs:
                job.schedule_removal()

            # Jadwalkan expire menu setelah 5 menit
            context.job_queue.run_once(
                expire_menu,
                when=MENU_EXPIRE_SECONDS,
                data={
                    "chat_id":    query.message.chat_id,
                    "message_id": query.message.message_id,
                    "user_id":    user.id,
                },
                name=f"expire_{user.id}",
            )

        else:
            logger.info("❌ Akses DITOLAK user %s (status: %s)", user.id, member.status)
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
# JOB: Expire menu channel setelah 5 menit
# ============================================================
async def expire_menu(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dipanggil otomatis setelah 5 menit — hapus tombol channel."""
    data       = context.job.data
    chat_id    = data["chat_id"]
    message_id = data["message_id"]
    user_id    = data["user_id"]

    channel_menu_time.pop(user_id, None)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                "⌛ *Menu channel sudah kadaluarsa\\.*\n\n"
                "Ketik /start untuk mendapatkan akses baru\\."
            ),
            parse_mode="MarkdownV2",
        )
        logger.info("Menu channel user %s sudah expired", user_id)
    except TelegramError as e:
        logger.warning("Gagal expire menu user %s: %s", user_id, e)

# ============================================================
# HANDLER: /id — hanya admin
# ============================================================
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        logger.warning("Akses /id ditolak untuk user %s", user.id)
        return

    chat = update.effective_chat
    await update.message.reply_text(
        f"👤 *User ID kamu* : `{user.id}`\n"
        f"💬 *Chat ID sekarang* : `{chat.id}`",
        parse_mode="Markdown",
    )

# ============================================================
# HANDLER: /status — hanya admin
# ============================================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        return

    try:
        chat = await context.bot.get_chat(GROUP_ID)
        me   = await context.bot.get_chat_member(GROUP_ID, context.bot.id)
        await update.message.reply_text(
            f"✅ *Bot terhubung ke grup:*\n"
            f"📌 Nama   : {chat.title}\n"
            f"🆔 ID     : `{chat.id}`\n"
            f"🤖 Status : `{me.status}`",
            parse_mode="Markdown",
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal cek grup: {e}")

# ============================================================
# GLOBAL ERROR HANDLER
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception saat handle update:", exc_info=context.error)

# ============================================================
# MAIN
# ============================================================
def main() -> None:
    logger.info("🚀 Bot dimulai...")

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("id",     get_id))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(check_access, pattern="^check$"))

    # Handler welcome — deteksi member baru join grup
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    app.add_error_handler(error_handler)

    logger.info("✅ Bot berjalan, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
