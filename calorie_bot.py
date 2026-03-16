#!/usr/bin/env python3
import os
import logging
import sqlite3
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from flask import Flask
from threading import Thread

# 🔐 ПОЛУЧАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logging.error("❌ Токен не найден! Установите переменную BOT_TOKEN")
    exit(1)

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Этапы разговора
WEIGHT, HEIGHT, AGE, GENDER, MAIN = range(5)

# База продуктов (калории на 100г)
FOODS = {
    "гречка": 343,
    "рис": 130,
    "курица": 165,
    "яйцо": 157,
    "банан": 89,
    "яблоко": 52,
    "творог": 121,
    "хлеб": 247,
    "картофель": 77,
    "помидор": 18,
    "огурец": 15,
    "сыр": 402,
    "молоко": 52,
    "йогурт": 59,
    "овсянка": 366,
    "макароны": 344,
    "рыба": 136,
    "говядина": 250,
    "свинина": 259,
    "колбаса": 310,
    "яичница": 180,
    "салат": 50,
    "суп": 80,
    "борщ": 90,
    "пельмени": 280,
    "пицца": 266,
    "шоколад": 546,
    "печенье": 417,
    "кофе": 2,
    "чай": 0,
    "сахар": 387,
    "орехи": 607,
    "авокадо": 160,
}


class SimpleCalorieBot:
    def __init__(self):
        self.init_database()

    def init_database(self):
        """Создаем простую базу данных"""
        try:
            self.conn = sqlite3.connect('calories.db')
            self.cursor = self.conn.cursor()

            # Таблица пользователей
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    weight REAL,
                    height REAL,
                    age INTEGER,
                    gender TEXT,
                    daily_goal INTEGER
                )
            ''')

            # Таблица еды
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    food TEXT,
                    calories INTEGER,
                    grams INTEGER,
                    date TEXT
                )
            ''')

            self.conn.commit()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")

    def save_user(self, user_id, weight, height, age, gender):
        """Сохраняем пользователя и считаем норму"""
        try:
            if gender == 'мужской':
                daily_goal = int(10 * weight + 6.25 * height - 5 * age + 5) * 1.2
            else:
                daily_goal = int(10 * weight + 6.25 * height - 5 * age - 161) * 1.2

            self.cursor.execute('''
                INSERT OR REPLACE INTO users
                (user_id, weight, height, age, gender, daily_goal)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, weight, height, age, gender, daily_goal))

            self.conn.commit()
            logger.info(f"✅ Пользователь {user_id} сохранён, норма: {daily_goal}")
            return daily_goal
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя: {e}")
            return 2000

    def add_food(self, user_id, food, grams):
        """Добавляем еду"""
        try:
            if food in FOODS:
                calories = int((FOODS[food] * grams) / 100)
                today = datetime.now().strftime('%Y-%m-%d')

                self.cursor.execute('''
                    INSERT INTO meals (user_id, food, calories, grams, date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, food, calories, grams, today))

                self.conn.commit()
                logger.info(f"✅ Добавлена еда: {food} {grams}г ({calories} ккал)")
                return calories
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка добавления еды: {e}")
            return None

    def get_today_total(self, user_id):
        """Считаем калории за сегодня"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')

            self.cursor.execute('''
                SELECT SUM(calories) FROM meals
                WHERE user_id=? AND date=?
            ''', (user_id, today))

            result = self.cursor.fetchone()
            return result[0] if result[0] else 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения калорий: {e}")
            return 0

    def get_goal(self, user_id):
        """Получаем дневную норму"""
        try:
            self.cursor.execute('SELECT daily_goal FROM users WHERE user_id=?', (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 2000
        except Exception as e:
            logger.error(f"❌ Ошибка получения нормы: {e}")
            return 2000

    def get_month_stats(self, user_id):
        """Статистика за месяц"""
        try:
            month = datetime.now().strftime('%Y-%m')

            self.cursor.execute('''
                SELECT date, SUM(calories) FROM meals
                WHERE user_id=? AND strftime('%Y-%m', date)=?
                GROUP BY date
                ORDER BY date
            ''', (user_id, month))

            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return []

    def user_exists(self, user_id):
        """Проверяем есть ли пользователь в базе"""
        try:
            self.cursor.execute('SELECT user_id FROM users WHERE user_id=?', (user_id,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки пользователя: {e}")
            return False


# Создаем бота
bot = SimpleCalorieBot()

# ========== ФУНКЦИИ БОТА ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало регистрации пользователя"""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} начал диалог")

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}! Я CalorieBot 🍏\n\n"
        "Я помогу тебе считать калории!\n\n"
        "Для начала расскажи немного о себе:\n"
        "Напиши свой **вес в кг** (например: 70)",
        parse_mode='Markdown'
    )
    return WEIGHT


async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем вес пользователя"""
    try:
        weight = float(update.message.text.replace(',', '.'))
        if weight < 20 or weight > 300:
            await update.message.reply_text("⚠️ Пожалуйста, введи корректный вес (20-300 кг)")
            return WEIGHT
        context.user_data['weight'] = weight
        logger.info(f"Вес: {weight}")
        await update.message.reply_text(
            f"✅ Вес: {weight} кг\n\n"
            "Теперь напиши свой **рост в см** (например: 175)",
            parse_mode='Markdown'
        )
        return HEIGHT
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, введи число (например: 70)")
        return WEIGHT


async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем рост пользователя"""
    try:
        height = float(update.message.text.replace(',', '.'))
        if height < 50 or height > 250:
            await update.message.reply_text("⚠️ Пожалуйста, введи корректный рост (50-250 см)")
            return HEIGHT
        context.user_data['height'] = height
        logger.info(f"Рост: {height}")
        await update.message.reply_text(
            f"✅ Рост: {height} см\n\n"
            "Теперь напиши свой **возраст в годах** (например: 30)",
            parse_mode='Markdown'
        )
        return AGE
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, введи число (например: 30)")
        return HEIGHT


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем возраст пользователя"""
    try:
        age = int(update.message.text)
        if age < 5 or age > 120:
            await update.message.reply_text("⚠️ Пожалуйста, введи корректный возраст (5-120 лет)")
            return AGE
        context.user_data['age'] = age
        logger.info(f"Возраст: {age}")
        await update.message.reply_text(
            f"✅ Возраст: {age} лет\n\n"
            "Выбери свой пол:\n"
            "👨 Мужской\n"
            "👩 Женский",
            reply_markup=ReplyKeyboardMarkup([['👨 Мужской', '👩 Женский']], one_time_keyboard=True)
        )
        return GENDER
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, введи число (например: 30)")
        return AGE


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем пол пользователя и завершаем регистрацию"""
    gender_text = update.message.text
    if 'Мужской' in gender_text:
        gender = 'мужской'
    elif 'Женский' in gender_text:
        gender = 'женский'
    else:
        await update.message.reply_text("⚠️ Пожалуйста, выбери пол из кнопок")
        return GENDER

    context.user_data['gender'] = gender
    logger.info(f"Пол: {gender}")

    # Сохраняем пользователя
    daily_goal = bot.save_user(
        update.effective_user.id,
        context.user_data['weight'],
        context.user_data['height'],
        context.user_data['age'],
        gender
    )

    await update.message.reply_text(
        f"🎉 Готово! Твоя норма: **{daily_goal} ккал/день**\n\n"
        "Теперь ты можешь:\n"
        "📸 Прислать фото еды — я рассчитаю калории\n"
        "✍️ Написать еду вручную (например: *гречка 200г*)\n"
        "📊 Узнать статистику\n\n"
        "Выбери действие:",
        reply_markup=ReplyKeyboardMarkup([
            ['🍽️ Добавить еду', '📊 Статистика'],
            ['❓ Помощь']
        ], resize_keyboard=True),
        parse_mode='Markdown'
    )
    return MAIN


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    text = update.message.text

    if text == '🍽️ Добавить еду':
        await update.message.reply_text(
            "📸 **Отправь фото еды** или напиши название и вес:\n"
            "Пример: *гречка 200г*, *яблоко 150г*",
            reply_markup=ReplyKeyboardMarkup([['🔙 Назад']], resize_keyboard=True),
            parse_mode='Markdown'
        )
        return 'ADD_FOOD'

    elif text == '📊 Статистика':
        user_id = update.effective_user.id
        today_calories = bot.get_today_total(user_id)
        daily_goal = bot.get_goal(user_id)
        remaining = daily_goal - today_calories

        await update.message.reply_text(
            f"📊 **Статистика за сегодня:**\n\n"
            f"🍽️ Съедено: **{today_calories} ккал**\n"
            f"🎯 Норма: **{daily_goal} ккал**\n"
            f"{'✅ Осталось: ' + str(remaining) + ' ккал' if remaining > 0 else '⚠️ Перебор: ' + str(-remaining) + ' ккал'}",
            reply_markup=ReplyKeyboardMarkup([['🍽️ Добавить еду', '📊 Статистика'], ['❓ Помощь']], resize_keyboard=True),
            parse_mode='Markdown'
        )
        return MAIN

    elif text == '❓ Помощь':
        await update.message.reply_text(
            "❓ **Помощь**\n\n"
            "📸 **Фото еды** — отправь фото, я рассчитаю калории\n"
            "✍️ **Ручной ввод** — напиши: *гречка 200г*, *яблоко 150г*\n"
            "📊 **Статистика** — посмотри сколько съел за день\n"
            "/start — начать заново\n"
            "/cancel — отменить текущее действие",
            parse_mode='Markdown'
        )
        return MAIN

    elif text == '🔙 Назад':
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=ReplyKeyboardMarkup([['🍽️ Добавить еду', '📊 Статистика'], ['❓ Помощь']], resize_keyboard=True)
        )
        return MAIN

    return MAIN


async def add_food_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик добавления еды (текст или фото)"""
    text = update.message.text

    # Кнопка "Назад"
    if text == '🔙 Назад':
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=ReplyKeyboardMarkup([['🍽️ Добавить еду', '📊 Статистика'], ['❓ Помощь']], resize_keyboard=True)
        )
        return MAIN

    # Парсим ввод: "гречка 200г" или "рис 150"
    match = re.match(r'([а-яА-ЯёЁ]+)\s*(\d+)(?:\s*г)?', text)
    if match:
        food = match.group(1).lower()
        grams = int(match.group(2))

        if food in FOODS:
            calories = bot.add_food(update.effective_user.id, food, grams)
            if calories:
                today_total = bot.get_today_total(update.effective_user.id)
                daily_goal = bot.get_goal(update.effective_user.id)

                await update.message.reply_text(
                    f"✅ **Добавлено:** {food.capitalize()} {grams}г = **{calories} ккал**\n\n"
                    f"📊 За сегодня: **{today_total}/{daily_goal} ккал**",
                    reply_markup=ReplyKeyboardMarkup([['🍽️ Добавить еду', '📊 Статистика'], ['❓ Помощь']], resize_keyboard=True),
                    parse_mode='Markdown'
                )
                return MAIN
            else:
                await update.message.reply_text("⚠️ Ошибка при добавлении. Попробуй еще раз.")
                return 'ADD_FOOD'
        else:
            # Продукт не найден, показываем список
            foods_list = ', '.join(list(FOODS.keys())[:10])
            await update.message.reply_text(
                f"⚠️ Продукт **{food}** не найден.\n\n"
                f"Доступные продукты: {foods_list}...\n\n"
                "Попробуй другой продукт или отправь фото.",
                parse_mode='Markdown'
            )
            return 'ADD_FOOD'

    # Не распознанный ввод
    await update.message.reply_text(
        "⚠️ Не понял формат.\n\n"
        "Напиши: **гречка 200г** или отправь 📸 фото еды.",
        parse_mode='Markdown'
    )
    return 'ADD_FOOD'


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = update.effective_user.id

    # Получаем фото
    photo = update.message.photo[-1]  # Самое большое фото

    await update.message.reply_text(
        "📸 Фото получено! Сейчас анализирую...\n\n"
        "⚠️ *Примечание: В данной версии бот не может точно определить калории по фото.*\n"
        "Пожалуйста, напиши что на фото и сколько грамм:\n"
        "Пример: *гречка 200г, курица 150г*",
        parse_mode='Markdown'
    )

    # Сохраняем фото (опционально)
    file = await photo.get_file()
    logger.info(f"Фото получено от пользователя {user_id}: {file.file_id}")

    return 'ADD_FOOD'


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    await update.message.reply_text(
        "❓ **Помощь**\n\n"
        "📸 **Фото еды** — отправь фото, я подскажу как посчитать\n"
        "✍️ **Ручной ввод** — напиши: *гречка 200г*, *яблоко 150г*\n"
        "📊 **Статистика** — посмотри сколько съел за день\n\n"
        "Доступные продукты:\n"
        f"{', '.join(list(FOODS.keys())[:15])}...\n\n"
        "/start — начать заново\n"
        "/cancel — отменить текущее действие",
        parse_mode='Markdown'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} отменил диалог")

    await update.message.reply_text(
        "❌ Действие отменено.\n\n"
        "Главное меню:",
        reply_markup=ReplyKeyboardMarkup([['🍽️ Добавить еду', '📊 Статистика'], ['❓ Помощь']], resize_keyboard=True)
    )
    return MAIN


# ========== KEEP-ALIVE ДЛЯ RAILWAY ==========
app_flask = Flask(__name__)


@app_flask.route('/')
def home():
    return "🍏 CalorieBot работает! /start в Telegram"


def run_web_server():
    """Запуск веб-сервера для Railway"""
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)


def start_bot():
    """Запуск Telegram бота"""
    try:
        application = Application.builder().token(TOKEN).build()

        # Настраиваем диалог
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
                HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
                GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
                MAIN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu),
                ],
                'ADD_FOOD': [
                    MessageHandler(filters.PHOTO, photo_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_food_handler),
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )

        # Добавляем обработчики
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('help', help_command))

        # Запускаем
        logger.info("🤖 Бот запущен!")
        application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")


def main():
    """Главная функция запуска"""
    # Запускаем веб-сервер в отдельном потоке
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

    # Запускаем бота в основном потоке
    start_bot()


if __name__ == '__main__':
    main()
