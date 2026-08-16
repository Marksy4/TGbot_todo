"""Точка входа в приложение."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from scheduler import setup_scheduler

from handlers import common, add_task, list_tasks


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    # 1. Готовим базу данных (создаём таблицу, если её ещё нет)
    await init_db()

    # 2. Создаём бота и диспетчер
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # 3. Подключаем роутеры с хэндлерами
    dp.include_router(common.router)
    dp.include_router(add_task.router)
    dp.include_router(list_tasks.router)

    # 4. Запускаем планировщик напоминаний
    setup_scheduler(bot)

    # 5. Сбрасываем возможные "зависшие" апдейты и запускаем long polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
