"""
Слой работы с базой данных.
Вся логика SQL-запросов вынесена сюда, хэндлеры не знают ничего про SQL.

ОПТИМИЗАЦИЯ ДЛЯ РАБОТЫ 24/7:
- Одно постоянное соединение вместо открытия нового на каждый запрос
  (открытие/закрытие соединения — самая дорогая операция в SQLite,
  особенно если бот работает месяцами и обрабатывает сотни запросов в день).
- WAL-режим (Write-Ahead Logging) — читатели не блокируют писателей,
  меньше нагрузка на диск ноутбука, устойчивее к внезапному завершению процесса.
- Индексы на часто используемые поля — запросы остаются быстрыми
  даже когда в БД накопятся тысячи задач.
"""
import aiosqlite
import logging
from datetime import datetime
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

# Формат хранения даты/времени дедлайна в БД (ISO-подобный, удобно сортировать как строку)
DT_FORMAT = "%Y-%m-%d %H:%M"

# Единое соединение на всё время жизни процесса.
# Инициализируется в init_db(), используется всеми функциями ниже.
_connection: Optional[aiosqlite.Connection] = None


async def init_db() -> None:
    """
    Открывает постоянное соединение с БД, включает WAL-режим,
    создаёт таблицу и индексы, если их ещё нет.
    Вызывается один раз при старте бота.
    """
    global _connection
    _connection = await aiosqlite.connect(DB_PATH)
    _connection.row_factory = aiosqlite.Row

    # WAL снижает нагрузку на диск и уменьшает риск повреждения БД
    # при внезапном выключении ноутбука/зависании системы.
    await _connection.execute("PRAGMA journal_mode=WAL")
    await _connection.execute("PRAGMA synchronous=NORMAL")

    await _connection.execute(
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

    # Индексы под наши реальные запросы:
    # - список задач пользователя фильтруется по (user_id, status)
    # - напоминания ищутся по (status, reminder_sent, deadline)
    await _connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status)"
    )
    await _connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_reminder ON tasks(status, reminder_sent, deadline)"
    )

    await _connection.commit()
    logger.info("База данных инициализирована (WAL-режим, индексы созданы)")


async def close_db() -> None:
    """Аккуратно закрывает соединение с БД. Вызывается при остановке бота."""
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
        logger.info("Соединение с БД закрыто")


def _db() -> aiosqlite.Connection:
    """Возвращает активное соединение или явно падает, если init_db() не был вызван."""
    if _connection is None:
        raise RuntimeError("БД не инициализирована — вызовите init_db() перед использованием")
    return _connection


async def add_task(
    user_id: int,
    title: str,
    category: str,
    difficulty: str,
    deadline: datetime,
) -> int:
    """Добавляет новую задачу в БД и возвращает её id."""
    cursor = await _db().execute(
        """
        INSERT INTO tasks (user_id, title, category, difficulty, deadline, status, reminder_sent)
        VALUES (?, ?, ?, ?, ?, 0, 0)
        """,
        (user_id, title, category, difficulty, deadline.strftime(DT_FORMAT)),
    )
    await _db().commit()
    return cursor.lastrowid


async def get_active_tasks(user_id: int) -> list[aiosqlite.Row]:
    """Возвращает все невыполненные задачи пользователя, отсортированные по дедлайну."""
    cursor = await _db().execute(
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
    cursor = await _db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    return await cursor.fetchone()


async def complete_task(task_id: int) -> None:
    """Помечает задачу выполненной."""
    await _db().execute("UPDATE tasks SET status = 1 WHERE id = ?", (task_id,))
    await _db().commit()


async def get_tasks_for_reminder(now: datetime, in_one_hour: datetime) -> list[aiosqlite.Row]:
    """
    Возвращает невыполненные задачи, дедлайн которых наступает в течение ближайшего часа
    и по которым напоминание ещё не отправлялось.
    """
    cursor = await _db().execute(
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
    await _db().execute("UPDATE tasks SET reminder_sent = 1 WHERE id = ?", (task_id,))
    await _db().commit()