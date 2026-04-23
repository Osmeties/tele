"""
Telegram Gate Bot - Full Secure Version
========================================
Fitur:
- PRIVATE CHAT : /join  → tombol join grup
- GRUP         : /akses → cek keanggotaan & menu channel (expire 5 menit)
- Welcome message + gambar saat member baru join grup
- /getfileid   → admin ambil file_id gambar (private chat)
- Rate limiting per user (5 request / 60 detik)
- Logging lengkap (terminal + file)
- Error handling spesifik
- Admin-only commands (/id, /status, /getfileid)
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
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import Forbidden, BadRequest, TelegramError

# ============================================================
# CONFIG
# ============================================================
TOKEN           = os.getenv("BOT_TOKEN")
GROUP_ID        = int(os.getenv("GROUP_ID", "0"))
ADMIN_ID        = int(os.getenv("ADMIN_ID", "0"))
GROUP_LINK      = os.getenv("GROUP_LINK", "https://t.me/+5uw96pDwyzphMjhh")
WELCOME_FILE_ID = os.getenv("WELCOME_FILE_ID", "")

if not TOKEN:
    raise EnvironmentError("❌ BOT_TOKEN tidak ditemukan!")
if GROUP_ID == 0:
    raise EnvironmentError("❌ GROUP_ID tidak ditemukan!")

# ============================================================
# CHANNELS
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
RATE_LIMIT          = 5
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
    now     = time.time()
    history = _rate_store[user_id]
    history[:] = [t for t in history if now - t < RATE_WINDOW]
    if len(history) >= RATE_LIMIT:
        return True
    history.append(now)
    return False

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def extract_status_change(chat_member_update: ChatMemberUpdated):
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    was_member = old_status in ("member", "administrator", "creator", "restricted")
    is_member  = new_status in ("member", "administrator", "creator", "restricted")
    return was_member, is_member

# ============================================================
# PRIVATE CHAT — /start (info awal)
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hanya aktif di private chat."""
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    logger.info("/start dari user %s (@%s)", user.id, user.username)

    await update.message.reply_text(
        "👋 Halo! Selamat datang di bot *Warkop Jam Rawan*\\.\n\n"
        "Gunakan perintah berikut:\n"
        "📌 /join  → Bergabung ke grup\n\n"
        "_Setelah join grup, ketik_ `/akses` _di dalam grup untuk akses channel\\._",
        parse_mode="MarkdownV2",
    )

# ============================================================
# PRIVATE CHAT — /join
# ============================================================
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hanya aktif di private chat — kasih tombol join grup."""
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    logger.info("/join dari user %s (@%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await update.message.reply_text("⏳ Terlalu banyak permintaan. Coba lagi nanti.")
        return

    keyboard = [
        [InlineKeyboardButton("📌 Join Grup Sekarang", url=GROUP_LINK)],
    ]
    await update.message.reply_text(
        "⚠️ Kamu belum join grup\\!\n\n"
        "Klik tombol di bawah untuk bergabung, "
        "lalu ketik `/akses` di dalam grup untuk akses channel\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ============================================================
# GRUP — /akses
# ============================================================
async def akses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hanya aktif di dalam grup — cek keanggotaan & tampilkan menu channel."""
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "⚠️ Perintah ini hanya bisa digunakan di dalam grup\\.",
            parse_mode="MarkdownV2",
        )
        return

    user = update.effective_user
    logger.info("/akses dari user %s (@%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await update.message.reply_text("⏳ Terlalu banyak permintaan. Coba lagi nanti.")
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)

        if member.status in ("member", "administrator", "creator"):
            logger.info("✅ Akses DIBERIKAN ke user %s", user.id)
            channel_menu_time[user.id] = time.time()

            keyboard = [
                [InlineKeyboardButton(name, url=link)]
                for name, link in CHANNELS.items()
            ]

            sent = await update.message.reply_text(
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
                    "chat_id":    sent.chat_id,
                    "message_id": sent.message_id,
                    "user_id":    user.id,
                },
                name=f"expire_{user.id}",
            )

        else:
            logger.info("❌ Akses DITOLAK user %s (status: %s)", user.id, member.status)
            keyboard = [
                [InlineKeyboardButton("📌 Join Grup", url=GROUP_LINK)],
            ]
            await update.message.reply_text(
                "❌ Kamu belum join grup\\!\n\n"
                "Join dulu lewat bot: /join di private chat\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except Forbidden:
        await update.message.reply_text("⚠️ Bot bukan admin grup\\. Hubungi admin\\.", parse_mode="MarkdownV2")
    except BadRequest as e:
        logger.error("BadRequest: %s", e)
        await update.message.reply_text("⚠️ Gagal memverifikasi\\. Coba lagi\\.", parse_mode="MarkdownV2")
    except TelegramError as e:
        logger.error("TelegramError: %s", e)
        await update.message.reply_text("⚠️ Error Telegram\\. Coba lagi\\.", parse_mode="MarkdownV2")

# ============================================================
# JOB: Expire menu channel setelah 5 menit
# ============================================================
async def expire_menu(context: ContextTypes.DEFAULT_TYPE) -> None:
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
                "Ketik /akses di grup untuk mendapatkan akses baru\\."
            ),
            parse_mode="MarkdownV2",
        )
        logger.info("Menu channel user %s sudah expired", user_id)
    except TelegramError as e:
        logger.warning("Gagal expire menu user %s: %s", user_id, e)

# ============================================================
# GRUP — Welcome member baru (dengan gambar)
# ============================================================
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    if was_member or not is_member:
        return

    user = update.chat_member.new_chat_member.user
    chat = update.effective_chat
    logger.info("Member baru join: %s (@%s)", user.id, user.username)

    mention = f"[{user.first_name}](tg://user?id={user.id})"

    welcome_text = (
        f"Selamat Datang {mention}\\! 👋\n\n"
        "WELCOME TO WARKOP JAM RAWAN\n"
        "🔥𝗧𝗘𝗠𝗣𝗔𝗧 𝗞𝗛𝗨𝗦𝗨𝗦 𝟭𝟴\\+🔥\n"
        "KONTEN INDO TERUPDATE\\!\\!\n"
        "GRATIS TINGGAL NONTON\n"
        "DISINI👇👇👇\n\n"
        "Ketik /akses di grup ini untuk akses channel\\!\n\n"
        "Bisa request video di WJR Group ✔️\n"
        "Update Setiap Hari ✔️\n"
        "GRATIS seumur hidup ✔️"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Akses Channel", callback_data="akses_welcome")],
    ])

    try:
        if WELCOME_FILE_ID:
            await context.bot.send_photo(
                chat_id=chat.id,
                photo=WELCOME_FILE_ID,
                caption=welcome_text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
        else:
            await context.bot.send_message(
                chat_id=chat.id,
                text=welcome_text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
    except TelegramError as e:
        logger.error("Gagal kirim welcome message: %s", e)

# ============================================================
# GRUP — Callback tombol "Akses Channel" dari welcome message
# ============================================================
async def akses_welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback tombol akses dari pesan welcome di grup."""
    query = update.callback_query
    user  = query.from_user
    await query.answer()

    if is_rate_limited(user.id):
        await query.answer("⏳ Terlalu sering. Tunggu sebentar.", show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)

        if member.status in ("member", "administrator", "creator"):
            logger.info("✅ Akses welcome DIBERIKAN ke user %s", user.id)
            channel_menu_time[user.id] = time.time()

            keyboard = [
                [InlineKeyboardButton(name, url=link)]
                for name, link in CHANNELS.items()
            ]
            await query.message.reply_text(
                "✅ Akses diberikan\\! Pilih channel:\n\n"
                "⏳ Menu ini aktif selama *5 menit*\\.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2",
            )

            sent = query.message

            old_jobs = context.job_queue.get_jobs_by_name(f"expire_{user.id}")
            for job in old_jobs:
                job.schedule_removal()

            context.job_queue.run_once(
                expire_menu,
                when=MENU_EXPIRE_SECONDS,
                data={
                    "chat_id":    sent.chat_id,
                    "message_id": sent.message_id,
                    "user_id":    user.id,
                },
                name=f"expire_{user.id}",
            )
        else:
            await query.answer("❌ Kamu belum join grup!", show_alert=True)

    except TelegramError as e:
        logger.error("TelegramError welcome callback: %s", e)
        await query.answer("⚠️ Error. Coba lagi.", show_alert=True)

# ============================================================
# PRIVATE CHAT — /getfileid (admin)
# ============================================================
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["waiting_photo"] = True
    await update.message.reply_text(
        "📸 Silakan kirim foto yang ingin dijadikan gambar welcome\\.\n\n"
        "Bot akan membalas dengan `file_id` foto tersebut\\.",
        parse_mode="MarkdownV2",
    )

# ============================================================
# PRIVATE CHAT — Terima foto dari admin
# ============================================================
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    if not is_admin(user.id):
        return
    if not context.user_data.get("waiting_photo"):
        return

    photo   = update.message.photo[-1]
    file_id = photo.file_id
    context.user_data["waiting_photo"] = False

    await update.message.reply_text(
        f"✅ *File ID foto kamu:*\n\n"
        f"`{file_id}`\n\n"
        f"📋 *Cara pakai:*\n"
        f"1\\. Copy `file_id` di atas\n"
        f"2\\. Buka Railway Dashboard → Variables\n"
        f"3\\. Tambahkan:\n"
        f"   Key: `WELCOME_FILE_ID`\n"
        f"   Value: \\(paste file\\_id\\)\n"
        f"4\\. Klik Deploy\\!",
        parse_mode="MarkdownV2",
    )
    logger.info("Admin %s mengambil file_id: %s", user.id, file_id)

# ============================================================
# PRIVATE CHAT — /id (admin)
# ============================================================
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    if not is_admin(user.id):
        return
    chat = update.effective_chat
    await update.message.reply_text(
        f"👤 *User ID kamu* : `{user.id}`\n"
        f"💬 *Chat ID sekarang* : `{chat.id}`",
        parse_mode="Markdown",
    )

# ============================================================
# PRIVATE CHAT — /status (admin)
# ============================================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
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

    # ── PRIVATE CHAT handlers ──────────────────────────────
    app.add_handler(CommandHandler("start",      start,      filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("join",       join,       filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("id",         get_id,     filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("status",     status,     filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("getfileid",  get_file_id,filters=filters.ChatType.PRIVATE))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, receive_photo))

    # ── GRUP handlers ──────────────────────────────────────
    app.add_handler(CommandHandler("akses", akses, filters=filters.ChatType.GROUPS))
    app.add_handler(CallbackQueryHandler(akses_welcome_callback, pattern="^akses_welcome$"))
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    app.add_error_handler(error_handler)

    logger.info("✅ Bot berjalan, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()