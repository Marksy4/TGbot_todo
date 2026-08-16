"""Общие команды: /start и /help."""
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="common")

HELP_TEXT = (
    "👋 Я твой личный таск-менеджер.\n\n"
    "Команды:\n"
    "/add — добавить новую задачу\n"
    "/list — показать активные задачи\n"
    "/help — показать это сообщение\n\n"
    "⏰ За час до дедлайна я пришлю напоминание."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)