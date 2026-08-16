"""Сборка inline-клавиатур для бота."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CATEGORIES

# Префиксы callback_data, чтобы разные группы кнопок не пересекались друг с другом
CATEGORY_PREFIX = "cat:"
DIFFICULTY_PREFIX = "diff:"
COMPLETE_PREFIX = "complete:"

# Отображаемое название сложности -> значение, которое кладём в БД
DIFFICULTY_OPTIONS = {
    "🟢 Легкая": "Легко",
    "🔴 Сложная": "Сложно",
}


def category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора категории задачи."""
    builder = InlineKeyboardBuilder()
    for category in CATEGORIES:
        builder.button(text=category, callback_data=f"{CATEGORY_PREFIX}{category}")
    builder.adjust(2)  # по 2 кнопки в ряд
    return builder.as_markup()


def difficulty_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора сложности задачи."""
    builder = InlineKeyboardBuilder()
    for label, value in DIFFICULTY_OPTIONS.items():
        builder.button(text=label, callback_data=f"{DIFFICULTY_PREFIX}{value}")
    builder.adjust(2)
    return builder.as_markup()


def complete_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой 'Выполнить' под конкретной задачей."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнить", callback_data=f"{COMPLETE_PREFIX}{task_id}")
    return builder.as_markup()
