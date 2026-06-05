"""
Telegram Gate Bot - Full Secure Version
========================================
Fitur:
- PRIVATE CHAT : /start → tombol join grup
- GRUP         : /akses → cek keanggotaan & menu channel (expire 5 menit, otomatis terhapus)
- Auto-delete pesan dengan kata terlarang (tanpa warn/kick)
- Welcome message + gambar saat member baru join grup
- /getfileid   → admin ambil file_id gambar (private chat)
- Rate limiting per user (5 request / 60 detik)
- Logging lengkap (terminal + file)
- Error handling spesifik
- Admin-only commands (/id, /status, /getfileid)
- Global error handler
"""

import os
import re
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
GROUP_LINK      = os.getenv("GROUP_LINK", "https://t.me/testingwjr")
WELCOME_FILE_ID = os.getenv("WELCOME_FILE_ID", "")

if not TOKEN:
    raise EnvironmentError("BOT_TOKEN tidak ditemukan!")
if GROUP_ID == 0:
    raise EnvironmentError("GROUP_ID tidak ditemukan!")

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
# KATA TERLARANG
# ============================================================
BANNED_WORDS = [
    "bokep","bkp","b0kep","b0k3p","porno","porn","p0rn","pornhub",
    "xnxx","xvideos","xvideo","redtube","youporn","jav","hentai",
    "doujin","ecchi","ahegao","nsfw","sex","seks","s3x","ngewe",
    "ngentot","ngntt","ng3nt0t","entot","ewean","memek","mmk","m3m3k",
    "kontol","kntl","k0nt0l","titit","ttt","penis","vagina","puki",
    "pukimak","pepek","toket","tete","tetek","payudara","boobs","nude",
    "bugil","telanjang","horny","sange","s4ng3","coli","colianku",
    "colmek","masturbasi","masturbate","onani","blowjob","bj","handjob",
    "hj","deepthroat","threesome","gangbang","anal","analsex","oral",
    "oralsex","milf","gilf","bdsm","fetish","crot","cum","cumming",
    "creampie","facial","fingering","petting","virgin","perawan",
    "jilboobs","jilmek","jilbabbugil","openbo","openbooking","bookingan",
    "openvc","vcbugil","livecolmek","camsex","camslut","camgirl",
    "camshow","onlyfans","ofans","stripper","striptease","lesbi",
    "lesbian","gaysex","bisex","transsex","shemale","tranny","pelacur",
    "lonte","perek","jablay","bohay","semok","toketgede","toketmontok",
    "ngocok","sepong","diwe","ngews","ewe","cabul","mesum","birahi",
    "birahian","bokongan","pantatmulus","pantatmontok","toketmulus",
    "kimcil","abgbugil","abgbokep","animehentai","bokepindo","bokepjepang",
    "bokepbarat","bokepviral","bokepterbaru","bokepremaja","bokepstreaming",
    "sexchat","sexcall","sexcam","sexvideo","sexmovie","sexstream",
    "adultvideo","adultchat","adultonly","r18","xxx","xxnx","xnx","xvid",
    "hotgirl","hotboy","hotmom","cewekbo","cewekopenbo","cowokgay",
    "cewekcoli","ceweksange","cowoksange","sangean","sangeberat","gairah",
    "nafsu","nafsubesar","ngaceng","ereksi","peju","sperma","mani",
    "vcsange","vctetek","vcporno","vcmesum","paptt","papkontol","papmemek",
    "sendnude","sendbokep","kirimbugil","openmichat","michatbo",
    "michatopenbo","escort","escorts","callgirl","cewekbispak","bispak",
    "ayamkampus","simpanan","jablaymurahan","pecun","ngeseks",
    "seksbebas","freesex","swinger","swingers","orgy","orgasm","orgasme",
    "moaning","desahan","desah","lendir","smean","colbar","colmekbareng",
    "ewebareng","gay","lesby","lesbong","bencong","banci","waria",
    "transeksual","shemaleporn","trannyporn","bokepanime","bokep3gp",
    "bokephd","bokep4k","bokepgratis","downloadbokep","linkbokep",
    "linkviral","linkmesum","link18","linkdewasa","kontensex",
    "kontendewasa","videomesum","videobokep","videoporno","filmdewasa",
    "filmsemi","semi","abgngentot","memekbasah","kontolbesar","toketbesar",
    "ngentotmemek","ngentotkontol","kontolhitam","memekpink","susugede",
    "tetekgede","tetekmontok","cewekbinal","cowokbirahi","wanitasange",
    "priasange","bokepjilbab","jilboob","ngocokbareng","ngewebareng",
    "colmekrame","sexparty","partysex","adultparty","adultgroup",
    "adultcontent","bokeptelegram","grupbokep","channelbokep",
    "videoviral18","mesumviral","bokepviralindo","cewekbugil","cowokbugil",
    "bugillive","livebugil","bugilindo","bugiljepang","bugilkorea",
    "bugilbarat","openboindo","openbomurah","openbovip","realescort",
    "escortindo","escortmurah","ngentotkeras","sexkeras","hardcore",
    "softcore","softporn","hardporn","pornografi","pornographic",
    "adultsite","adultweb","adultforum","adultgram","bokepgroup",
    "bokepchannel","pornchannel","pornsite","sexsite","sexforum",
    "pornforum","livesex","liveporn","pornlive","videocoli","videocrot",
    "videohentai","hentaivideo","hentaiporn","animeporno","animebugil",
    "doujin18","javuncensored","uncensored","javhd","javsubindo","javindo",
    "javstream","javdownload","pornindo","pornjepang","pornbarat",
    "pornkorea","pornthai","sexindo","sexjepang","sexbarat","sexviral",
    "linkngentot","linksex","linkporn","linkhentai","linkjav","grupmesum",
    "grupdewasa","grup18","grouporn","groupsex","groupmesum","cewekbokep",
    "cowokbokep","bugilviral","viral18","viralbokep","viralporno",
    "ngewekeras","toketseksi","pantatseksi","cewekseksi","cowokseksi",
    "cewekganjen","cowokmesum","nafsuan","sangetotal","openvcsange",
    "vccoli","vcpap","papbugil","papbokep","papmesum","papnude",
    "sendnudes","jualbokep","jualvideo","jualkonten","jualonlyfans",
    "jualvc","jualpap","jualbugil","jualmesum","jualporno",
    "jualakunonlyfans","pecunthai","di entot","colisetiap hari",
    "colbar yuk","vcdong","papdong","papttdong",
]

# Buat regex pattern sekali saja saat startup
_BANNED_PATTERN = re.compile(
    r"(?<![a-z0-9])(" +
    "|".join(re.escape(w) for w in sorted(BANNED_WORDS, key=len, reverse=True)) +
    r")(?![a-z0-9])",
    re.IGNORECASE,
)

# ============================================================
# KONSTANTA
# ============================================================
RATE_LIMIT             = 5
RATE_WINDOW            = 60
MENU_EXPIRE_SECONDS    = 300   # 5 menit
WELCOME_DELETE_SECONDS = 1800  # 30 menit

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

def contains_banned_word(text: str) -> bool:
    return bool(_BANNED_PATTERN.search(text))

def extract_status_change(chat_member_update: ChatMemberUpdated):
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    was_member = old_status in ("member", "administrator", "creator", "restricted")
    is_member  = new_status in ("member", "administrator", "creator", "restricted")
    return was_member, is_member

# ============================================================
# GRUP — Filter pesan kata terlarang (delete only)
# ============================================================
async def filter_banned_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-delete pesan yang mengandung kata terlarang. Tanpa warn/kick."""
    msg = update.message or update.edited_message
    if not msg:
        return

    # Hanya proses pesan di grup utama
    if msg.chat.id != GROUP_ID:
        return

    # Ambil teks atau caption
    text = msg.text or msg.caption or ""
    if not text:
        return

    # Admin grup bebas dari filter
    user = msg.from_user
    if not user:
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)
        if member.status in ("administrator", "creator"):
            return
    except TelegramError:
        pass

    if not contains_banned_word(text):
        return

    # Hapus pesan diam-diam (tanpa notifikasi apapun)
    try:
        await msg.delete()
        logger.info(
            "Pesan dihapus dari user %s (@%s) | teks: %s",
            user.id, user.username, text[:60]
        )
    except TelegramError as e:
        logger.warning("Gagal hapus pesan dari user %s: %s", user.id, e)

# ============================================================
# JOB: Expire menu — hapus pesan otomatis setelah 5 menit
# ============================================================
async def expire_menu(context: ContextTypes.DEFAULT_TYPE) -> None:
    data       = context.job.data
    chat_id    = data["chat_id"]
    message_id = data["message_id"]
    user_id    = data["user_id"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info("Menu channel user %s berhasil dihapus", user_id)
    except TelegramError:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⌛ Menu channel sudah kadaluarsa.\n\nKetik /akses untuk akses baru.",
            )
        except TelegramError as e:
            logger.warning("Gagal expire menu user %s: %s", user_id, e)

# ============================================================
# JOB: Auto-delete welcome message setelah 30 menit
# ============================================================
async def expire_welcome(context: ContextTypes.DEFAULT_TYPE) -> None:
    data       = context.job.data
    chat_id    = data["chat_id"]
    message_id = data["message_id"]
    user_id    = data["user_id"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info("Welcome message user %s berhasil dihapus (30 menit)", user_id)
    except TelegramError as e:
        logger.warning("Gagal hapus welcome message user %s: %s", user_id, e)

# ============================================================
# HELPER: Kirim menu channel + jadwalkan expire
# ============================================================
async def send_channel_menu(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    reply_to_message_id: int | None = None,
) -> None:
    old_jobs = context.job_queue.get_jobs_by_name(f"expire_{user_id}")
    for job in old_jobs:
        job.schedule_removal()

    keyboard = [
        [InlineKeyboardButton(name, url=link)]
        for name, link in CHANNELS.items()
    ]

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "✅ Akses diberikan! Pilih channel:\n\n"
            "⏳ Menu ini aktif selama 5 menit dan akan otomatis terhapus."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=reply_to_message_id,
    )

    if context.job_queue is None:
        logger.error("job_queue tidak aktif! Pastikan APScheduler terinstall: pip install 'python-telegram-bot[job-queue]'")
    else:
        context.job_queue.run_once(
            expire_menu,
            when=MENU_EXPIRE_SECONDS,
            data={"chat_id": sent.chat_id, "message_id": sent.message_id, "user_id": user_id},
            name=f"expire_{user_id}",
        )
    logger.info("Menu channel dikirim ke user %s", user_id)

# ============================================================
# PRIVATE CHAT — /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    logger.info("/start dari user %s (@%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await update.message.reply_text("⏳ Terlalu banyak permintaan. Coba lagi nanti.")
        return

    keyboard = [[InlineKeyboardButton("📌 Join Grup Sekarang", url=GROUP_LINK)]]
    await update.message.reply_text(
        "👋 Halo! Selamat datang di bot Warkop Jam Rawan!\n\n"
        "⚠️ Kamu harus join grup dulu sebelum bisa akses channel.\n\n"
        "Klik tombol di bawah untuk bergabung, "
        "lalu ketik /akses di dalam grup untuk akses channel.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ============================================================
# GRUP — /akses
# ============================================================
async def akses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Perintah ini hanya bisa digunakan di dalam grup.")
        return

    user = update.effective_user
    logger.info("/akses dari user %s (@%s)", user.id, user.username)

    if is_rate_limited(user.id):
        await update.message.reply_text("⏳ Terlalu banyak permintaan. Coba lagi nanti.")
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)

        if member.status in ("member", "administrator", "creator"):
            logger.info("Akses DIBERIKAN ke user %s", user.id)
            await send_channel_menu(
                context=context,
                chat_id=update.effective_chat.id,
                user_id=user.id,
                reply_to_message_id=update.message.message_id,
            )
        else:
            keyboard = [[InlineKeyboardButton("📌 Join Grup", url=GROUP_LINK)]]
            await update.message.reply_text(
                "❌ Kamu belum join grup!\n\n"
                "Chat bot secara pribadi dan ketik /start untuk link join.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except Forbidden:
        await update.message.reply_text("⚠️ Bot bukan admin grup. Hubungi admin.")
    except BadRequest as e:
        logger.error("BadRequest: %s", e)
        await update.message.reply_text("⚠️ Gagal memverifikasi. Coba lagi.")
    except TelegramError as e:
        logger.error("TelegramError: %s", e)
        await update.message.reply_text("⚠️ Error Telegram. Coba lagi.")

# ============================================================
# GRUP — Callback tombol "Akses Channel" dari welcome message
# ============================================================
async def akses_welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = query.from_user
    await query.answer()

    if is_rate_limited(user.id):
        await query.answer("⏳ Terlalu sering. Tunggu sebentar.", show_alert=True)
        return

    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)
        if member.status in ("member", "administrator", "creator"):
            await send_channel_menu(context=context, chat_id=query.message.chat_id, user_id=user.id)
        else:
            await query.answer("❌ Kamu belum join grup!", show_alert=True)
    except TelegramError as e:
        logger.error("TelegramError welcome callback: %s", e)
        await query.answer("⚠️ Error. Coba lagi.", show_alert=True)

# ============================================================
# GRUP — Welcome member baru
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

    # Hanya proses dari grup utama, bukan linked channel
    if chat.id != GROUP_ID:
        logger.info("Abaikan update dari chat %s (bukan grup utama)", chat.id)
        return

    logger.info("Member baru join: %s (@%s)", user.id, user.username)

    mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
    welcome_text = (
        f"Selamat Datang {mention}! 👋\n\n"
        "WELCOME TO WARKOP JAM RAWAN\n"
        "🔥𝗧𝗘𝗠𝗣𝗔𝗧 𝗞𝗛𝗨𝗦𝗨𝗦 𝟭𝟴+🔥\n"
        "KONTEN INDO TERUPDATE!!\n"
        "GRATIS TINGGAL NONTON\n"
        "DISINI👇👇👇\n\n"
        "Ketik /akses di grup ini untuk akses channel!\n\n"
        "Bisa request video di WJR Group ✔️\n"
        "Update Setiap Hari ✔️\n"
        "GRATIS seumur hidup ✔️"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Akses Channel", callback_data="akses_welcome")]
    ])

    try:
        if WELCOME_FILE_ID:
            sent = await context.bot.send_photo(
                chat_id=chat.id, photo=WELCOME_FILE_ID,
                caption=welcome_text, parse_mode="HTML", reply_markup=keyboard,
            )
        else:
            sent = await context.bot.send_message(
                chat_id=chat.id, text=welcome_text,
                parse_mode="HTML", reply_markup=keyboard,
            )

        # Jadwalkan auto-delete welcome message setelah 30 menit
        if context.job_queue is None:
            logger.error("job_queue tidak aktif! Pastikan APScheduler terinstall.")
        else:
            context.job_queue.run_once(
                expire_welcome,
                when=WELCOME_DELETE_SECONDS,
                data={"chat_id": chat.id, "message_id": sent.message_id, "user_id": user.id},
                name=f"expire_welcome_{user.id}",
            )
        logger.info("Welcome message dikirim ke user %s, akan dihapus dalam 30 menit", user.id)
    except TelegramError as e:
        logger.error("Gagal kirim welcome message: %s", e)

# ============================================================
# PRIVATE CHAT — /getfileid (admin)
# ============================================================
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private" or not is_admin(update.effective_user.id):
        return
    context.user_data["waiting_photo"] = True
    await update.message.reply_text(
        "📸 Silakan kirim foto yang ingin dijadikan gambar welcome.\n"
        "Bot akan membalas dengan file_id foto tersebut."
    )

# ============================================================
# PRIVATE CHAT — Terima foto dari admin
# ============================================================
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private" or not is_admin(update.effective_user.id):
        return
    if not context.user_data.get("waiting_photo"):
        return

    file_id = update.message.photo[-1].file_id
    context.user_data["waiting_photo"] = False

    await update.message.reply_text(
        f"✅ File ID foto kamu:\n\n{file_id}\n\n"
        f"Cara pakai:\n"
        f"1. Copy file_id di atas\n"
        f"2. Buka Railway Dashboard → Variables\n"
        f"3. Key: WELCOME_FILE_ID | Value: (paste file_id)\n"
        f"4. Klik Deploy!"
    )
    logger.info("Admin mengambil file_id: %s", file_id)

# ============================================================
# PRIVATE CHAT — /id (admin)
# ============================================================
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private" or not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        f"User ID kamu    : {update.effective_user.id}\n"
        f"Chat ID sekarang: {update.effective_chat.id}"
    )

# ============================================================
# PRIVATE CHAT — /status (admin)
# ============================================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private" or not is_admin(update.effective_user.id):
        return
    try:
        chat = await context.bot.get_chat(GROUP_ID)
        me   = await context.bot.get_chat_member(GROUP_ID, context.bot.id)
        await update.message.reply_text(
            f"✅ Bot terhubung ke grup:\n"
            f"Nama   : {chat.title}\n"
            f"ID     : {chat.id}\n"
            f"Status : {me.status}"
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
    logger.info("Bot dimulai...")

    app = ApplicationBuilder().token(TOKEN).build()

    # Validasi job_queue aktif saat startup
    if app.job_queue is None:
        raise RuntimeError(
            "job_queue tidak aktif! "
            "Jalankan: pip install 'python-telegram-bot[job-queue]'"
        )
    logger.info("job_queue aktif ✓")

    # ── PRIVATE CHAT ───────────────────────────────────────
    app.add_handler(CommandHandler("start",     start,       filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("id",        get_id,      filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("status",    status,      filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("getfileid", get_file_id, filters=filters.ChatType.PRIVATE))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, receive_photo))

    # ── GRUP ───────────────────────────────────────────────
    app.add_handler(CommandHandler("akses", akses, filters=filters.ChatType.GROUPS))
    app.add_handler(CallbackQueryHandler(akses_welcome_callback, pattern="^akses_welcome$"))
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Filter kata terlarang — teks biasa dan caption (foto/video)
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS,
        filter_banned_words
    ))

    app.add_error_handler(error_handler)

    logger.info("Bot berjalan, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
