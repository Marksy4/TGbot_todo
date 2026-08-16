"""Точка входа в приложение."""
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db, close_db
from scheduler import setup_scheduler

from handlers import common, add_task, list_tasks


def setup_logging() -> None:
    """
    Логи одновременно идут в консоль и в файл bot.log.
    Ротация: файл не растёт бесконечно (важно для запуска месяцами на одном ноутбуке) —
    максимум 5 МБ на файл, хранится 3 последних файла.
    """
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # aiohttp/aiogram сами логируют довольно много служебной информации — приглушаем до WARNING,
    # чтобы не засорять лог и не тратить лишнее время на дисковый ввод-вывод
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


async def start_health_server() -> None:
    """
    Мини-веб-сервер только для хостингов типа Render, которым нужен открытый порт
    и HTTP-ответы, чтобы не "усыплять" бесплатный сервис (не мешает работе локально/на VPS).
    Слушает порт из переменной окружения PORT (Render передаёт его сам).
    """
    port = int(os.getenv("PORT", 0))
    if not port:
        return  # Локально/на VPS переменной PORT нет — сервер просто не поднимаем

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="Bot is running")

    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logging.info("Health-check сервер запущен на порту %s", port)


async def run_bot() -> None:
    """Готовит и запускает бота (одна попытка — обёртка с перезапуском ниже)."""
    # 1. Готовим базу данных (создаём таблицу и подключение, если их ещё нет)
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

    try:
        # 5. Поднимаем health-check сервер (если PORT задан хостингом) и polling
        await start_health_server()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        # Даже если polling упал с ошибкой — закрываем сессию бота и БД аккуратно,
        # чтобы не оставлять "подвисшие" соединения при следующем перезапуске.
        await bot.session.close()
        await close_db()


async def main() -> None:
    """
    Супервизор: если run_bot() упадёт из-за временной проблемы (например,
    ноутбук на секунду потерял Wi-Fi), процесс не завершится, а перезапустит бота
    через паузу — это и есть "устойчивость 24/7" на обычном ноутбуке без внешнего
    менеджера служб.
    """
    setup_logging()
    logger = logging.getLogger("supervisor")

    retry_delay = 5  # секунд; при повторных сбоях подряд увеличивается (backoff)
    max_retry_delay = 300  # не ждать больше 5 минут между попытками

    while True:
        try:
            logger.info("Запуск бота...")
            await run_bot()
            # Если start_polling вернулся без исключения — значит, это штатная
            # остановка (например, Ctrl+C), выходим из супервизора.
            logger.info("Бот остановлен штатно.")
            break
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Получен сигнал остановки, завершаю работу.")
            break
        except Exception:
            logger.exception(
                "Бот упал с ошибкой. Перезапуск через %s секунд.", retry_delay
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
        else:
            retry_delay = 5  # сбрасываем задержку после успешного запуска


if __name__ == "__main__":
    asyncio.run(main())