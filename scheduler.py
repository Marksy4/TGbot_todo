"""
Планировщик напоминаний.
Раз в минуту проверяет БД и шлёт сообщение, если до дедлайна задачи остался час или меньше.
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db

logger = logging.getLogger(__name__)


async def check_deadlines(bot: Bot) -> None:
    """Job, который выполняется каждую минуту."""
    now = datetime.now()
    in_one_hour = now + timedelta(hours=1)

    tasks = await db.get_tasks_for_reminder(now, in_one_hour)

    for task in tasks:
        try:
            await bot.send_message(
                chat_id=task["user_id"],
                text=(
                    "⏰ <b>Напоминание!</b>\n\n"
                    f"Задача «{task['title']}» скоро истекает.\n"
                    f"📅 Дедлайн: {task['deadline']}"
                ),
                parse_mode="HTML",
            )
            # Отмечаем, что напоминание отправлено, чтобы не слать его каждую минуту
            await db.mark_reminder_sent(task["id"])
        except Exception as e:
            # Например, пользователь заблокировал бота — не роняем весь job из-за одной задачи
            logger.warning("Не удалось отправить напоминание по задаче %s: %s", task["id"], e)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Создаёт и запускает планировщик с job'ом проверки дедлайнов раз в минуту."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_deadlines, trigger="interval", minutes=1, args=(bot,))
    scheduler.start()
    return scheduler