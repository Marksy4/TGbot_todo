"""Состояния конечного автомата (FSM) для диалога добавления задачи."""
from aiogram.fsm.state import State, StatesGroup


class AddTaskStates(StatesGroup):
    waiting_title = State()       # ждём текст задачи
    waiting_category = State()    # ждём выбор категории (inline-кнопка)
    waiting_difficulty = State()  # ждём выбор сложности (inline-кнопка)
    waiting_deadline = State()    # ждём дату/время дедлайна