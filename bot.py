import asyncio
from aiogram import Bot, Dispatcher
from config import load_config
from database.db import Database
from database.repositories import Repository
from handlers import start, context, projects, folders, parts, notes, files

async def main_run():
    config = load_config()
    database = Database(config.db_path)
    await database.init()
    repo = Repository(database)

    start.setup(repo)
    context.setup(repo)
    projects.setup(repo)
    folders.setup(repo)
    parts.setup(repo)
    notes.setup(repo)
    files.setup(repo)

    bot = Bot(config.bot_token)
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(projects.router)
    dp.include_router(folders.router)
    dp.include_router(parts.router)
    dp.include_router(notes.router)
    dp.include_router(files.router)

    print("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main_run())
    except KeyboardInterrupt:
        pass
