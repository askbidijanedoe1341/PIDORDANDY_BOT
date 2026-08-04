import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Задайте переменную окружения BOT_TOKEN")

PORT = int(os.environ.get("PORT", 8080))

saved_videos = {}
spam_tasks = {}

# ---------- Telegram-команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Бот-спамер видео и гифок.\n\n"
        "📎 По ссылке:\n"
        "  /spam <URL> [кол-во] [gif|video]\n"
        "  /spam_forever <URL> [gif|video]\n"
        "  /stop — остановить бесконечный спам\n\n"
        "💾 С сохранённым видео:\n"
        "  /set_video — загрузить видео в бота\n"
        "  /spam_saved [кол-во]\n"
        "  /spam_forever_saved\n"
        "⬇️ /download — имитация скачивания и спам (10 раз)"
    )

async def spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Укажите URL: /spam <url> [кол-во] [gif|video]")
        return
    url = args[0]
    count = 5
    media_type = "gif"
    for arg in args[1:]:
        if arg.isdigit():
            count = int(arg)
        elif arg.lower() in ("gif", "video"):
            media_type = arg.lower()
    chat_id = update.effective_chat.id
    bot = context.bot
    for _ in range(count):
        if media_type == "video":
            await bot.send_video(chat_id=chat_id, video=url)
        else:
            await bot.send_animation(chat_id=chat_id, animation=url)
        await asyncio.sleep(0.3)
    await update.message.reply_text(f"Отправлено {count} раз(а) как {media_type}")

async def spam_forever(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Укажите URL: /spam_forever <url> [gif|video]")
        return
    url = args[0]
    media_type = "gif"
    if len(args) > 1 and args[1].lower() in ("gif", "video"):
        media_type = args[1].lower()
    chat_id = update.effective_chat.id
    bot = context.bot
    if chat_id in spam_tasks:
        spam_tasks[chat_id].cancel()
    task = asyncio.create_task(forever_spam(bot, chat_id, url, media_type, False))
    spam_tasks[chat_id] = task
    await update.message.reply_text(f"Бесконечный спам запущен ({media_type}). Остановка /stop")

async def set_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📤 Пришлите видео в ответ на это сообщение.")
    context.user_data['waiting_video'] = True

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_video'):
        return
    chat_id = update.effective_chat.id
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("Это не видео. Пришлите видеофайл.")
        return
    saved_videos[chat_id] = video.file_id
    context.user_data['waiting_video'] = False
    await update.message.reply_text("✅ Видео сохранено! Теперь можно спамить им через /spam_saved или /download")

async def spam_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    file_id = saved_videos.get(chat_id)
    if not file_id:
        await update.message.reply_text("Сначала сохраните видео через /set_video")
        return
    count = 5
    args = context.args
    if args and args[0].isdigit():
        count = int(args[0])
    bot = context.bot
    for _ in range(count):
        await bot.send_video(chat_id=chat_id, video=file_id)
        await asyncio.sleep(0.3)
    await update.message.reply_text(f"Сохранённое видео отправлено {count} раз")
async def spam_forever_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    file_id = saved_videos.get(chat_id)
    if not file_id:
        await update.message.reply_text("Сначала сохраните видео через /set_video")
        return
    bot = context.bot
    if chat_id in spam_tasks:
        spam_tasks[chat_id].cancel()
    task = asyncio.create_task(forever_spam(bot, chat_id, file_id, "video", True))
    spam_tasks[chat_id] = task
    await update.message.reply_text("Бесконечный спам сохранённым видео запущен. Остановка /stop")

async def forever_spam(bot, chat_id, media, media_type, is_saved):
    while True:
        try:
            if media_type == "video":
                await bot.send_video(chat_id=chat_id, video=media)
            else:
                await bot.send_animation(chat_id=chat_id, animation=media)
            await asyncio.sleep(0.5)
        except Exception:
            break

async def stop_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    task = spam_tasks.pop(chat_id, None)
    if task:
        task.cancel()
        await update.message.reply_text("Спам остановлен")
    else:
        await update.message.reply_text("Активного спама нет")

# ---------- НОВАЯ КОМАНДА /download ----------
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    file_id = saved_videos.get(chat_id)
    if not file_id:
        await update.message.reply_text("❌ Сначала сохраните видео через /set_video")
        return

    # Отправляем сообщение о начале загрузки
    msg = await update.message.reply_text("📥 Начинаю скачивание видео... 0%")
    # Имитация прогресса
    for percent in range(10, 101, 10):
        await asyncio.sleep(0.5)
        await msg.edit_text(f"📥 Скачивание видео... {percent}%")
    await msg.edit_text("✅ Скачивание завершено! Начинаю показ...")
    await asyncio.sleep(0.5)

    # Спамим сохранённым видео 10 раз
    bot = context.bot
    for _ in range(10):
        await bot.send_video(chat_id=chat_id, video=file_id)
        await asyncio.sleep(0.3)
    await update.message.reply_text("🎉 Все видео отправлены!")

# ---------- Веб-сервер для пингов ----------
async def handle_ping(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Веб-сервер запущен на порту {PORT}")

# ---------- Главный запуск ----------
async def main():
    asyncio.create_task(start_web_server())

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("spam", spam))
    application.add_handler(CommandHandler("spam_forever", spam_forever))
    application.add_handler(CommandHandler("set_video", set_video))
    application.add_handler(CommandHandler("spam_saved", spam_saved))
    application.add_handler(CommandHandler("spam_forever_saved", spam_forever_saved))
    application.add_handler(CommandHandler("stop", stop_spam))
    application.add_handler(CommandHandler("download", download))  # <-- новая команда
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
