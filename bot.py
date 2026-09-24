import asyncio
from aiogram import Bot, Dispatcher
from config import load_config
from database.db import Database
from database.repositories import Repository
from handlers import start, main

async def main_run():
    config = load_config()
    database = Database(config.db_path)
    await database.init()
    repo = Repository(database)

    start.setup(repo)
    main.setup(repo)

    bot = Bot(config.bot_token)
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(main.router)

    print("Bot started. Press Ctrl+C to stop.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main_run())
    except KeyboardInterrupt:
        pass
