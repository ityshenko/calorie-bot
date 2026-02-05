#!/usr/bin/env python3
import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, ContextTypes, filters
)
from flask import Flask
from threading import Thread

# 🔐 ПОЛУЧАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (БЕЗОПАСНО!)
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
            return 2000  # Значение по умолчанию
    
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

# Создаем бота
bot = SimpleCalorieBot()

# ========== ФУНКЦИИ БОТА ==========
# [ВСЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ: start, get_weight, get_height, get_age, 
#  get_gender, main_menu, choose_food, get_grams, help_command, cancel]
# [Скопируйте их сюда без изменений, как у вас были]

# ⚠️ ВАЖНО: Скопируйте сюда ВСЕ ваши функции бота из предыдущего кода
# от "async def start" до "async def cancel" включительно
# Я оставил это место для вашего кода функций

# ========== ВАШ КОД ФУНКЦИЙ ЗДЕСЬ ==========
# [Вставьте сюда ВСЕ ваши функции, начиная с async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):]
# [и заканчивая async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):]

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
                MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
                'CHOOSE_FOOD': [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_food)],
                'GET_GRAMS': [MessageHandler(filters.TEXT & ~filters.COMMAND, get_grams)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        
        # Добавляем обработчики
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('help', help_command))
        
        # Запускаем
        logger.info("🤖 Бот запущен на Railway!")
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