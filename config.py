"""
Конфигурация проекта.
Токен бота НИКОГДА не хранится в коде — только в .env (который не должен попадать в git).
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "Не найден BOT_TOKEN. Скопируйте .env.example в .env и впишите туда токен бота."
    )

# Путь к файлу базы данных SQLite
DB_PATH = "tasks.db"

# Список доступных категорий задач (можно менять под себя)
CATEGORIES = ["Учеба", "Код", "Быт"]
