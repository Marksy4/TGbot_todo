"""Хэндлеры для команды /list — вывод активных задач и их завершение."""
from collections import defaultdict

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards import complete_keyboard, COMPLETE_PREFIX

router = Router(name="list_tasks")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    """Выводит все невыполненные задачи пользователя, сгруппированные по категориям."""
    tasks = await db.get_active_tasks(message.from_user.id)

    if not tasks:
        await message.answer("🎉 У вас нет активных задач!")
        return

    # Группируем задачи по категориям
    grouped: dict[str, list] = defaultdict(list)
    for task in tasks:
        grouped[task["category"]].append(task)

    await message.answer(f"📋 Ваши активные задачи ({len(tasks)}):")

    # Каждую задачу выводим отдельным сообщением с кнопкой "Выполнить",
    # чтобы кнопка однозначно относилась к одной конкретной задаче.
    for category, category_tasks in grouped.items():
        await message.answer(f"📂 <b>{category}</b>", parse_mode="HTML")
        for task in category_tasks:
            difficulty_icon = "🔴" if task["difficulty"] == "Сложно" else "🟢"
            text = (
                f"{difficulty_icon} <b>{task['title']}</b>\n"
                f"⚙️ Сложность: {task['difficulty']}\n"
                f"📅 Дедлайн: {task['deadline']}"
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=complete_keyboard(task["id"]),
            )


@router.callback_query(F.data.startswith(COMPLETE_PREFIX))
async def process_complete(callback: CallbackQuery) -> None:
    """Помечает задачу выполненной и удаляет сообщение с ней из чата."""
    task_id = int(callback.data.removeprefix(COMPLETE_PREFIX))

    task = await db.get_task(task_id)
    # Проверяем, что задача существует и принадлежит именно этому пользователю
    if task is None or task["user_id"] != callback.from_user.id:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    await db.complete_task(task_id)
    await callback.message.delete()
    await callback.answer("Задача выполнена! ✅")
