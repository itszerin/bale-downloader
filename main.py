# bot_download.py
import asyncio
from functools import partial
from pathlib import Path
import aiohttp
from aiohttp import ClientTimeout
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "848833428:qfwjlJsnFdfXdkHG7mwY22EmCkR1ih3TViE"
TEMP_DIR = Path("tmp_files")
TEMP_DIR.mkdir(exist_ok=True)

async def stream_download(url: str, dest_path: Path, session: aiohttp.ClientSession):
    """دانلود استریم و ذخیره روی دیسک (chunked)."""
    timeout = ClientTimeout(total=None)  # بدون تایم‌اوت کلی
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()
        with dest_path.open("wb") as f:
            async for chunk in resp.content.iter_chunked(64*1024):
                if not chunk:
                    break
                f.write(chunk)
    return dest_path

async def sendfile_from_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler برای /get <url>"""
    if not context.args:
        await update.message.reply_text("لطفاً یک لینک مستقیم بفرستید: /get <url>")
        return

    url = context.args[0]
    msg = await update.message.reply_text("در حال دانلود...")

    filename = url.split("/")[-1] or "file"
    # امن‌تر: محدودیت طول اسم و حذف کاراکترهای مشکل‌ساز
    filename = filename.split("?")[0][:120]
    dest = TEMP_DIR / filename

    try:
        async with aiohttp.ClientSession() as session:
            await stream_download(url, dest, session)

        # برای جلوگیری از load زیاد حافظه، فایل را از دیسک باز می‌کنیم
        with dest.open("rb") as f:
            # InputFile از فایل‌باینری پشتیبانی می‌کند
            await update.message.reply_document(document=InputFile(f, filename=filename))

        await msg.edit_text("تمام شد ✅")

    except Exception as e:
        await msg.edit_text(f"خطا هنگام دانلود/ارسال: {e}")

    finally:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک مستقیم فایل بدید با دستور:\n/get <url>")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get", sendfile_from_url))
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
