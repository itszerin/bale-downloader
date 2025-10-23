import aiohttp
import asyncio
import time
import humanize
from pathlib import Path
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "848833428:qfwjlJsnFdfXdkHG7mwY22EmCkR1ih3TViE"   # ← توکن خودت را اینجا بگذار
TEMP_DIR = Path("tmp_files")
TEMP_DIR.mkdir(exist_ok=True)

async def download_with_progress(url: str, dest: Path, update_func):
    """دانلود استریم فایل با گزارش پیشرفت و سرعت"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            chunk_size = 128 * 1024  # 128KB

            downloaded = 0
            start_time = time.time()
            last_report_time = start_time
            last_downloaded = 0

            with dest.open("wb") as f:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_report_time >= 3:
                        elapsed = now - start_time
                        speed = (downloaded - last_downloaded) / (now - last_report_time + 1e-6)
                        percent = (downloaded / total * 100) if total else 0
                        await update_func(downloaded, total, speed, percent)
                        last_report_time = now
                        last_downloaded = downloaded

    return dest

async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📎 لطفاً لینک مستقیم فایل را وارد کنید:\nمثال: /get https://example.com/file.zip")
        return

    url = context.args[0]
    filename = url.split("/")[-1].split("?")[0] or "file"
    dest = TEMP_DIR / filename

    msg = await update.message.reply_text("🚀 شروع دانلود...")

    async def progress(downloaded, total, speed, percent):
        human_downloaded = humanize.naturalsize(downloaded, binary=True)
        human_total = humanize.naturalsize(total, binary=True)
        human_speed = humanize.naturalsize(speed, binary=True)
        await msg.edit_text(
            f"⬇️ در حال دانلود...\n"
            f"📁 فایل: `{filename}`\n"
            f"📊 پیشرفت: {percent:.2f}%\n"
            f"💾 {human_downloaded} / {human_total}\n"
            f"⚡ سرعت: {human_speed}/s",
            parse_mode="Markdown"
        )

    try:
        await download_with_progress(url, dest, progress)

        # دانلود تمام شد، فایل را ارسال کن
        await msg.edit_text("📤 ارسال فایل...")
        with dest.open("rb") as f:
            await update.message.reply_document(document=InputFile(f, filename=filename))
        await msg.edit_text("✅ دانلود و ارسال انجام شد!")

    except Exception as e:
        await msg.edit_text(f"❌ خطا: {e}")

    finally:
        if dest.exists():
            dest.unlink(missing_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام 👋\nلینک فایل را با دستور زیر بفرست:\n/get <لینک مستقیم>")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get", get_command))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
