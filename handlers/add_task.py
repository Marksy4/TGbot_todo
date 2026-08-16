"""Хэндлеры для команды /add — пошаговое добавление задачи через FSM."""
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import database as db
from states import AddTaskStates
from keyboards import (
    category_keyboard,
    difficulty_keyboard,
    CATEGORY_PREFIX,
    DIFFICULTY_PREFIX,
)

router = Router(name="add_task")


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    """Шаг 1: старт сценария — просим ввести текст задачи."""
    await state.clear()  # на случай, если пользователь бросил предыдущий диалог на середине
    await message.answer("📝 Введите текст задачи:")
    await state.set_state(AddTaskStates.waiting_title)


@router.message(StateFilter(AddTaskStates.waiting_title))
async def process_title(message: Message, state: FSMContext) -> None:
    """Получили текст задачи -> предлагаем выбрать категорию."""
    title = (message.text or "").strip()
    if not title:
        await message.answer("Текст задачи не может быть пустым. Введите ещё раз:")
        return

    await state.update_data(title=title)
    await message.answer("📂 Выберите категорию:", reply_markup=category_keyboard())
    await state.set_state(AddTaskStates.waiting_category)


@router.callback_query(StateFilter(AddTaskStates.waiting_category), F.data.startswith(CATEGORY_PREFIX))
async def process_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 2: выбрали категорию -> предлагаем выбрать сложность."""
    category = callback.data.removeprefix(CATEGORY_PREFIX)
    await state.update_data(category=category)

    await callback.message.edit_text(
        f"📂 Категория: {category}\n\n⚙️ Выберите сложность:",
        reply_markup=difficulty_keyboard(),
    )
    await state.set_state(AddTaskStates.waiting_difficulty)
    await callback.answer()


@router.callback_query(StateFilter(AddTaskStates.waiting_difficulty), F.data.startswith(DIFFICULTY_PREFIX))
async def process_difficulty(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 3: выбрали сложность -> просим ввести дедлайн."""
    difficulty = callback.data.removeprefix(DIFFICULTY_PREFIX)
    await state.update_data(difficulty=difficulty)

    await callback.message.edit_text(
        f"⚙️ Сложность: {difficulty}\n\n"
        "📅 Введите дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 25.12.2026 18:30"
    )
    await state.set_state(AddTaskStates.waiting_deadline)
    await callback.answer()


@router.message(StateFilter(AddTaskStates.waiting_deadline))
async def process_deadline(message: Message, state: FSMContext) -> None:
    """Шаг 4: парсим дедлайн, сохраняем задачу в БД, завершаем диалог."""
    raw_text = (message.text or "").strip()

    try:
        deadline = datetime.strptime(raw_text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(
            "⚠️ Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.12.2026 18:30"
        )
        return

    if deadline <= datetime.now():
        await message.answer("⚠️ Дедлайн должен быть в будущем. Введите дату ещё раз:")
        return

    data = await state.get_data()

    task_id = await db.add_task(
        user_id=message.from_user.id,
        title=data["title"],
        category=data["category"],
        difficulty=data["difficulty"],
        deadline=deadline,
    )

    await message.answer(
        "✅ Задача добавлена!\n\n"
        f"<b>{data['title']}</b>\n"
        f"📂 Категория: {data['category']}\n"
        f"⚙️ Сложность: {data['difficulty']}\n"
        f"📅 Дедлайн: {deadline.strftime('%d.%m.%Y %H:%M')}\n"
        f"🆔 ID: {task_id}",
        parse_mode="HTML",
    )
    await state.clear()