"""
Слой работы с базой данных.
Вся логика SQL-запросов вынесена сюда, хэндлеры не знают ничего про SQL.
"""
import aiosqlite
from datetime import datetime
from typing import Optional

from config import DB_PATH

# Формат хранения даты/времени дедлайна в БД (ISO-подобный, удобно сортировать как строку)
DT_FORMAT = "%Y-%m-%d %H:%M"


async def init_db() -> None:
    """
    Создаёт таблицу tasks, если она ещё не существует.
    Вызывается один раз при старте бота.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                title         TEXT    NOT NULL,
                category      TEXT    NOT NULL,
                difficulty    TEXT    NOT NULL,
                deadline      TEXT    NOT NULL,   -- хранится строкой в формате DT_FORMAT
                status        INTEGER NOT NULL DEFAULT 0,  -- 0 = не выполнена, 1 = выполнена
                reminder_sent INTEGER NOT NULL DEFAULT 0   -- чтобы не слать напоминание повторно
            )
            """
        )
        await db.commit()


async def add_task(
    user_id: int,
    title: str,
    category: str,
    difficulty: str,
    deadline: datetime,
) -> int:
    """Добавляет новую задачу в БД и возвращает её id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO tasks (user_id, title, category, difficulty, deadline, status, reminder_sent)
            VALUES (?, ?, ?, ?, ?, 0, 0)
            """,
            (user_id, title, category, difficulty, deadline.strftime(DT_FORMAT)),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_tasks(user_id: int) -> list[aiosqlite.Row]:
    """Возвращает все невыполненные задачи пользователя, отсортированные по дедлайну."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, title, category, difficulty, deadline
            FROM tasks
            WHERE user_id = ? AND status = 0
            ORDER BY category, deadline
            """,
            (user_id,),
        )
        return await cursor.fetchall()


async def get_task(task_id: int) -> Optional[aiosqlite.Row]:
    """Возвращает одну задачу по id (нужно, например, чтобы проверить владельца перед удалением)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return await cursor.fetchone()


async def complete_task(task_id: int) -> None:
    """Помечает задачу выполненной."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET status = 1 WHERE id = ?", (task_id,))
        await db.commit()


async def get_tasks_for_reminder(now: datetime, in_one_hour: datetime) -> list[aiosqlite.Row]:
    """
    Возвращает невыполненные задачи, дедлайн которых наступает в течение ближайшего часа
    и по которым напоминание ещё не отправлялось.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, title, deadline
            FROM tasks
            WHERE status = 0
              AND reminder_sent = 0
              AND deadline BETWEEN ? AND ?
            """,
            (now.strftime(DT_FORMAT), in_one_hour.strftime(DT_FORMAT)),
        )
        return await cursor.fetchall()


async def mark_reminder_sent(task_id: int) -> None:
    """Отмечает, что напоминание по задаче уже отправлено (чтобы не дублировать)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET reminder_sent = 1 WHERE id = ?", (task_id,))
        await db.commit()
