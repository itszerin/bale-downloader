import aiohttp
import asyncio
import time
import humanize
from pathlib import Path
from telegram import (
    Update,
    InputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = "848833428:qfwjlJsnFdfXdkHG7mwY22EmCkR1ih3TViE"  # ← توکن خودت
TEMP_DIR = Path("tmp_files")
TEMP_DIR.mkdir(exist_ok=True)

# برای نگه داشتن وظایف فعال
ACTIVE_DOWNLOADS = {}

# --------------------------------------------------------------

async def download_with_progress(url, dest, progress_cb, cancel_event):
    """دانلود با پیشرفت و قابلیت لغو"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            chunk_size = 128 * 1024
            downloaded = 0
            start_time = time.time()
            last_update = start_time
            last_downloaded = 0

            with dest.open("wb") as f:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    if cancel_event.is_set():
                        return False  # لغو شد
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_update >= 3:
                        speed = (downloaded - last_downloaded) / (now - last_update + 1e-6)
                        percent = downloaded / total * 100 if total else 0
                        await progress_cb(downloaded, total, speed, percent)
                        last_update = now
                        last_downloaded = downloaded
    return True

# --------------------------------------------------------------

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هنگام زدن دکمه لغو"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("⏹ لغو در حال انجام...")

    task_info = ACTIVE_DOWNLOADS.get(user_id)
    if not task_info:
        await query.edit_message_text("⚠️ هیچ دانلود فعالی یافت نشد.")
        return

    # علامت لغو بگذار
    task_info["cancel"].set()

    await query.edit_message_text("❌ دانلود لغو شد.")
    dest = task_info["dest"]
    if dest.exists():
        dest.unlink(missing_ok=True)
    ACTIVE_DOWNLOADS.pop(user_id, None)

# --------------------------------------------------------------

async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /get"""
    if not context.args:
        await update.message.reply_text("📎 لینک مستقیم فایل را بده:\n/get <url>")
        return

    url = context.args[0]
    filename = url.split("/")[-1].split("?")[0] or "file"
    dest = TEMP_DIR / filename
    user_id = update.effective_user.id
    cancel_event = asyncio.Event()

    # ذخیره برای مدیریت لغو
    ACTIVE_DOWNLOADS[user_id] = {"cancel": cancel_event, "dest": dest}

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("لغو ❌", callback_data="cancel_download")]]
    )
    msg = await update.message.reply_text("🚀 شروع دانلود...", reply_markup=keyboard)

    async def progress(downloaded, total, speed, percent):
        human_downloaded = humanize.naturalsize(downloaded, binary=True)
        human_total = humanize.naturalsize(total, binary=True)
        human_speed = humanize.naturalsize(speed, binary=True)
        try:
            await msg.edit_text(
                f"⬇️ در حال دانلود...\n"
                f"📁 `{filename}`\n"
                f"📊 {percent:.2f}%\n"
                f"💾 {human_downloaded} / {human_total}\n"
                f"⚡ {human_speed}/s",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            pass  # اگر همزمان با لغو conflict شد، نادیده بگیر

    async def task():
        try:
            ok = await download_with_progress(url, dest, progress, cancel_event)
            if not ok:
                return  # لغو شد
            await msg.edit_text("📤 ارسال فایل...", reply_markup=None)
            with dest.open("rb") as f:
                await update.message.reply_document(InputFile(f, filename=filename))
            await msg.edit_text("✅ دانلود و ارسال انجام شد!", reply_markup=None)
        except Exception as e:
            await msg.edit_text(f"❌ خطا: {e}", reply_markup=None)
        finally:
            ACTIVE_DOWNLOADS.pop(user_id, None)
            if dest.exists():
                dest.unlink(missing_ok=True)

    # اجرای دانلود در task جدا
    asyncio.create_task(task())

# --------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام 👋\nبا دستور زیر لینک فایل بده:\n/get <url>")

# --------------------------------------------------------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get", get_command))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern="cancel_download"))
    print("🤖 Bot started and ready.")
    app.run_polling()

# --------------------------------------------------------------

if __name__ == "__main__":
    main()
