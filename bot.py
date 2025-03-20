import random
import os
import asyncio
import logging
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReactionTypeEmoji
from openai import AsyncOpenAI
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from functools import partial
import asyncpg
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Версия кода
CODE_VERSION = "2.7"

# Константы
MAX_TOKENS = 999
AI_TEMPERATURE = 1.5
CHAT_HISTORY_LIMIT = 30
TARGET_CHAT_ID = -1002362736664  # Чат, в котором сохраняем всю историю

# Получение переменных окружения
def get_env_var(var_name, default=None):
    value = os.getenv(var_name)
    if value is None and default is None:
        logger.error(f"Отсутствует обязательная переменная окружения: {var_name}")
        sys.exit(1)
    return value if value is not None else default

# Токены и ключи
TELEGRAM_TOKEN = get_env_var('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = get_env_var('DEEPSEEK_API_KEY')
OPENWEATHER_API_KEY = get_env_var('OPENWEATHER_API_KEY')
RAPIDAPI_KEY = get_env_var('RAPIDAPI_KEY')
CHAT_ID = int(get_env_var('CHAT_ID'))
DATABASE_URL = get_env_var('DATABASE_URL')
TARGET_USER_ID = int(get_env_var('TARGET_USER_ID', '660949286'))

# Константы для ответов из .env
RESPONSES_SOSAL = json.loads(get_env_var('RESPONSES_SOSAL'))  # Обязательная переменная
RARE_RESPONSE_SOSAL = get_env_var('RARE_RESPONSE_SOSAL')      # Обязательная переменная
RESPONSE_LETAL = get_env_var('RESPONSE_LETAL')                # Обязательная переменная
RESPONSES_SCAMIL = json.loads(get_env_var('RESPONSES_SCAMIL'))  # Обязательная переменная
TEAM_IDS = json.loads(get_env_var('TEAM_IDS'))                # Обязательная переменная
TARGET_REACTION = ReactionTypeEmoji(emoji=get_env_var('TARGET_REACTION'))  # Обязательная переменная

# Настройка клиента DeepSeek
deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Класс для всех API-запросов
class ApiClient:
    @staticmethod
    async def get_weather(city):
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        temp = data['main']['temp']
                        desc = data['weather'][0]['description']
                        return f"{temp}°C, {desc}"
                    logger.error(f"Ошибка получения погоды для {city}: {response.status}")
                    return "Нет данных"
        except aiohttp.ClientError as e:
            logger.error(f"Исключение при получении погоды: {e}")
            return "Нет данных"

    @staticmethod
    async def get_currency_rates():
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        usd_byn = data['usd'].get('byn', 0)
                        usd_rub = data['usd'].get('rub', 0)
                        return usd_byn, usd_rub
                    logger.error(f"Ошибка получения курсов валют: {response.status}")
                    return 0, 0
        except aiohttp.ClientError as e:
            logger.error(f"Исключение при получении курсов валют: {e}")
            return 0, 0

    @staticmethod
    async def get_crypto_prices():
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,worldcoin&vs_currencies=usd"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        btc_price = data.get('bitcoin', {}).get('usd', 0)
                        wld_price = data.get('worldcoin', {}).get('usd', 0)
                        return btc_price, wld_price
                    logger.error(f"Ошибка получения цен криптовалют: {response.status}")
                    return 0, 0
        except aiohttp.ClientError as e:
            logger.error(f"Исключение при получении цен криптовалют: {e}")
            return 0, 0

    @staticmethod
    async def get_team_matches(team_id):
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures?team={team_id}&last=5"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.error(f"Ошибка API-Football для команды {team_id}: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Исключение при запросе матчей: {e}")
            return None

    @staticmethod
    async def get_match_events(fixture_id):
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/events?fixture={fixture_id}"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"События для матча {fixture_id}: {data}")
                        return data
                    logger.error(f"Ошибка API-Football для событий матча {fixture_id}: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Исключение при запросе событий матча: {e}")
            return None

# Класс для работы с AI
class AiHandler:
    @staticmethod
    async def get_ai_response(chat_history, query):
        try:
            messages = [
                {"role": "system", "content": f"Ты Анатолий Шарий, твоя фамилия Шарий, у тебя есть жена Ольга Шарий. Ты пророссийский журналист, скамер, блогер, эксцентричный пиздец, любишь материться. Сегодня {datetime.now().strftime('%Y-%m-%d')}. Отвечай с иронией, надменностью и будь полезным помощником в Telegram-группе."}
            ] + chat_history + [{"role": "user", "content": query}]
            response = await deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=AI_TEMPERATURE
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            return f"Ошибка, ёбана: {str(e)}"

# Класс для отправки утренних сообщений
class MorningMessageSender:
    def __init__(self, bot):
        self.bot = bot

   async def send_morning_message(self):
    logger.info("Подготовка утреннего сообщения")
    try:
        # Получаем данные о погоде и курсах валют как обычно
        cities = {
            "Минск": "Minsk,BY", "Жлобин": "Zhlobin,BY", "Гомель": "Gomel,BY",
            "Житковичи": "Zhitkovichi,BY", "Шри-Ланка": "Colombo,LK", "Ноябрьск": "Noyabrsk,RU"
        }
        weather_tasks = [ApiClient.get_weather(code) for code in cities.values()]
        weather_results, (usd_byn_rate, usd_rub_rate), (btc_price_usd, wld_price_usd) = await asyncio.gather(
            asyncio.gather(*weather_tasks, return_exceptions=True),
            ApiClient.get_currency_rates(),
            ApiClient.get_crypto_prices()
        )
        weather_data = dict(zip(cities.keys(), weather_results))

        btc_price_byn = float(btc_price_usd) * float(usd_byn_rate) if btc_price_usd and usd_byn_rate else 0
        wld_price_byn = float(wld_price_usd) * float(usd_byn_rate) if wld_price_usd and usd_byn_rate else 0

        # Формируем базовое сообщение
        base_message = (
            "*Положняк по погоде:*\n"
            + "\n".join(f"🌥 *{city}*: {data}" for city, data in weather_data.items()) + "\n\n"
            "*Положняк по курсам:*\n"
            f"💵 *USD/BYN*: {usd_byn_rate:.2f} BYN\n"
            f"💵 *USD/RUB*: {usd_rub_rate:.2f} RUB\n"
            f"₿ *BTC*: ${btc_price_usd:,.2f} USD | {btc_price_byn:,.2f} BYN\n"
            f"🌍 *WLD*: ${wld_price_usd:.2f} USD | {wld_price_byn:.2f} BYN"
        )
        
        # Генерируем персонализированный комментарий на основе данных
        # Определяем показатели для комментария
        avg_temp = sum([float(data.split('°')[0]) for data in weather_data.values() if '°' in data]) / len(weather_data)
        btc_change = random.uniform(-5, 5)  # Симуляция изменения курса
        
        # Запрашиваем комментарий от AI
        ai_prompt = f"""
        Сегодня средняя температура в городах {avg_temp:.1f}°C.
        Курс USD/BYN: {usd_byn_rate:.2f}, USD/RUB: {usd_rub_rate:.2f}.
        Биткоин стоит ${btc_price_usd:,.2f} USD с изменением {btc_change:.1f}%.
        Напиши короткое приветствие для утреннего сообщения в групповой чат, учитывая эти данные.
        Будь остроумным и немного саркастичным. Максимум 2-3 предложения.
        """
        
        ai_response = await AiHandler.get_ai_response([], ai_prompt)
        
        # Формируем итоговое сообщение
        final_message = f"{ai_response}\n\n{base_message}"
        
        sent_message = await self.bot.send_message(chat_id=CHAT_ID, text=final_message, parse_mode=types.ParseMode.MARKDOWN)
        logger.info("Утреннее сообщение отправлено")
        return sent_message
    except Exception as e:
        logger.error(f"Ошибка при отправке утреннего сообщения: {e}")

class ContextManager:
    def __init__(self, db_pool, history_limit=100):
        self.db_pool = db_pool
        self.history_limit = history_limit
        self.last_bot_message_time = {}
        self.conversation_topics = {}
        self.random_intervention_chance = 0.05  # 5% шанс вмешаться

    async def process_message(self, message, bot_id):
        chat_id = message.chat.id
        user_id = message.from_user.id
        message_text = message.text
        
        # Сохраняем все сообщения в базу для контекста
        await self.save_message(chat_id, user_id, message_text)
        
        # Обновляем текущие темы разговора
        self._update_conversation_topics(chat_id, message_text)
        
        # Проверяем, нужно ли боту вмешаться
        should_intervene = False
        
        # Не вмешиваемся, если сообщение от бота
        if user_id != bot_id:
            # Случайное вмешательство с низкой вероятностью
            should_intervene = random.random() < self.random_intervention_chance
            
            # Не вмешиваемся, если бот недавно писал
            if chat_id in self.last_bot_message_time:
                time_since_last = time.time() - self.last_bot_message_time[chat_id]
                if time_since_last < 300:  # 5 минут
                    should_intervene = False
        
        return should_intervene
    
    async def get_context(self, chat_id, limit=10):
        # Получаем последние сообщения из базы для контекста
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, content 
                FROM chat_history 
                WHERE chat_id = $1 
                ORDER BY timestamp DESC 
                LIMIT $2
                """,
                chat_id, limit
            )
            
            # Форматируем контекст для AI
            context = "Последние сообщения в группе:\n\n"
            for row in reversed(rows):
                user_type = "Бот" if row['user_id'] == bot_id else "Пользователь"
                context += f"{user_type}: {row['content']}\n"
            
            return context
    
    def _update_conversation_topics(self, chat_id, text):
        # Простой анализ тем разговора
        # Можно расширить с помощью NLP или ключевых слов
        if chat_id not in self.conversation_topics:
            self.conversation_topics[chat_id] = []

# Основной класс бота
class BotApp:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.dp = Dispatcher()
        self.scheduler = None
        self.morning_sender = None
        self.keep_alive_task = None
        self.db_pool = None
        self.bot_info = None

    async def keep_alive(self):
        while True:
            logger.info("Бот активен")
            await asyncio.sleep(300)

    async def cleanup_old_messages(self):
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM chat_history WHERE timestamp < EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')"
                )
            logger.info("Очистка старых сообщений завершена")
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка PostgreSQL при очистке старых сообщений: {e}")

    async def on_startup(self):
        logger.info(f"Запуск бота версии {CODE_VERSION}")
        self.bot_info = await self.bot.get_me()
        self.morning_sender = MorningMessageSender(self.bot)
        self.db_pool = await asyncpg.create_pool(DATABASE_URL)
        async with self.db_pool.acquire() as conn:
            # Создаём таблицу chat_history с колонкой reset_id
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT,
                    user_id BIGINT,
                    message_id BIGINT,
                    role TEXT,
                    content TEXT CHECK (LENGTH(content) <= 4000),
                    timestamp DOUBLE PRECISION,
                    reset_id INTEGER DEFAULT 0
                )
            """)
            # Создаём таблицу для хранения reset_id для каждого чата
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_reset_ids (
                    chat_id BIGINT PRIMARY KEY,
                    reset_id INTEGER DEFAULT 0
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id ON chat_history (chat_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history (timestamp)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_reset_id ON chat_history (reset_id)")
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        self.scheduler.add_job(self.morning_sender.send_morning_message, trigger=CronTrigger(hour=17, minute=53))
        self.scheduler.add_job(self.cleanup_old_messages, trigger=CronTrigger(hour=0, minute=0))  # Очистка каждую полночь
        self.scheduler.start()
        logger.info("Планировщик запущен")
        self.keep_alive_task = asyncio.create_task(self.keep_alive())

    async def on_shutdown(self):
        logger.info("Остановка бота")
        if self.keep_alive_task and not self.keep_alive_task.done():
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Соединение с PostgreSQL закрыто")
        await self.bot.session.close()
        logger.info("Бот остановлен")

    async def get_reset_id(self, chat_id):
        async with self.db_pool.acquire() as conn:
            reset_id = await conn.fetchval(
                "SELECT reset_id FROM chat_reset_ids WHERE chat_id = $1",
                chat_id
            )
            if reset_id is None:
                # Если записи нет, создаём с reset_id = 0
                await conn.execute(
                    "INSERT INTO chat_reset_ids (chat_id, reset_id) VALUES ($1, 0) ON CONFLICT (chat_id) DO NOTHING",
                    chat_id
                )
                return 0
            return reset_id

    async def increment_reset_id(self, chat_id):
        async with self.db_pool.acquire() as conn:
            # Увеличиваем reset_id на 1, если запись существует, или создаём новую
            await conn.execute(
                """
                INSERT INTO chat_reset_ids (chat_id, reset_id)
                VALUES ($1, 1)
                ON CONFLICT (chat_id)
                DO UPDATE SET reset_id = chat_reset_ids.reset_id + 1
                """,
                chat_id
            )
            new_reset_id = await conn.fetchval(
                "SELECT reset_id FROM chat_reset_ids WHERE chat_id = $1",
                chat_id
            )
            return new_reset_id

    async def get_chat_history(self, chat_id):
        reset_id = await self.get_reset_id(chat_id)
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content
                FROM chat_history
                WHERE chat_id = $1 AND reset_id = $2
                ORDER BY timestamp DESC
                LIMIT $3
                """,
                chat_id, reset_id, CHAT_HISTORY_LIMIT
            )
            return [{"role": row['role'], "content": row['content']} for row in reversed(rows)]

    async def save_chat_message(self, chat_id, user_id, message_id, role, content):
        try:
            content = content.encode('utf-8', 'ignore').decode('utf-8')
            content = content[:4000] if len(content) > 4000 else content
            reset_id = await self.get_reset_id(chat_id)
            logger.info(f"Сохранение сообщения: chat_id={chat_id}, user_id={user_id}, message_id={message_id}, role={role}, reset_id={reset_id}, content={content[:50]}...")
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO chat_history (chat_id, user_id, message_id, role, content, timestamp, reset_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    chat_id, user_id, message_id, role, content, datetime.now().timestamp(), reset_id
                )
            logger.info(f"Сообщение успешно сохранено: chat_id={chat_id}, user_id={user_id}, message_id={message_id}, role={role}, reset_id={reset_id}")
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка PostgreSQL при сохранении сообщения: {e}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка при сохранении сообщения: {e}")
            raise

    async def command_start(self, message: types.Message):
        sent_message = await message.reply(f"Привет, я бот версии {CODE_VERSION}")
        if message.chat.id == TARGET_CHAT_ID:
            await self.save_chat_message(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", f"Привет, я бот версии {CODE_VERSION}")

    async def command_version(self, message: types.Message):
        sent_message = await message.reply(f"Версия бота: {CODE_VERSION}")
        if message.chat.id == TARGET_CHAT_ID:
            await self.save_chat_message(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", f"Версия бота: {CODE_VERSION}")

    async def command_reset(self, message: types.Message):
        chat_id = message.chat.id
        await self.increment_reset_id(chat_id)
        sent_message = await message.reply("Контекст для AI сброшен, мудила. Начинаем с чистого листа!")
        if chat_id == TARGET_CHAT_ID:
            await self.save_chat_message(chat_id, self.bot_info.id, sent_message.message_id, "assistant", "Контекст для AI сброшен, мудила. Начинаем с чистого листа!")

    async def command_team_matches(self, message: types.Message, team_name):
        team_id = TEAM_IDS.get(team_name)
        if not team_id:
            sent_message = await message.reply("Команда не найдена, мудила!")
            if message.chat.id == TARGET_CHAT_ID:
                await self.save_chat_message(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", "Команда не найдена, мудила!")
            return
        data = await ApiClient.get_team_matches(team_id)
        if not data or not data.get("response"):
            sent_message = await message.reply("Не удалось получить данные о матчах. Пиздец какой-то!")
            if message.chat.id == TARGET_CHAT_ID:
                await self.save_chat_message(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", "Не удалось получить данные о матчах. Пиздец какой-то!")
            return
        response = f"Последние 5 матчей {team_name.upper()}:\n\n"
        for fixture in data["response"]:
            fixture_id = fixture["fixture"]["id"]
            home_team = fixture["teams"]["home"]["name"]
            away_team = fixture["teams"]["away"]["name"]
            home_goals = fixture["goals"]["home"] if fixture["goals"]["home"] is not None else 0
            away_goals = fixture["goals"]["away"] if fixture["goals"]["away"] is not None else 0
            date = fixture["fixture"]["date"].split("T")[0]
            result_icon = ("🟢" if home_goals > away_goals else "🔴" if home_goals < away_goals else "🟡") \
                if fixture["teams"]["home"]["id"] == team_id else \
                ("🟢" if away_goals > home_goals else "🔴" if away_goals < home_goals else "🟡")
            events_data = await ApiClient.get_match_events(fixture_id)
            goals_str = "Голы: "
            if events_data and events_data.get("response"):
                goal_events = [e for e in events_data["response"] if e["type"] == "Goal"]
                goals_str += ", ".join([f"{e['player']['name']} ({e['time']['elapsed']}')" for e in goal_events]) \
                    if goal_events else "Нет данных о голах"
            else:
                goals_str += "Ошибка получения событий"
            response += f"{result_icon} {date}: {home_team} {home_goals} - {away_goals} {away_team}\n{goals_str}\n\n"
        sent_message = await message.reply(response)
        if message.chat.id == TARGET_CHAT_ID:
            await self.save_chat_message(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", response)

async def handle_message(self, message: types.Message):
    try:
        if not message.from_user or not message.text:
            return
        
        message_text = message.text.lower()
        bot_username = f"@{self.bot_info.username.lower()}"
        bot_id = self.bot_info.id
        chat_id = message.chat.id
        user_id = message.from_user.id
        message_id = message.message_id

        # Сохраняем сообщение
        await self.save_chat_message(chat_id, user_id, message_id, "user", message.text)
        
        # Проверяем, нужно ли боту вмешаться
        should_intervene = await self.context_manager.process_message(message, bot_id)
        
        # Проверяем особые случаи
        if message_text in ['сосал?', 'sosal?']:
            # Обработка особых случаев...
        
        # Обработка сообщений с тегом или ответом
        is_reply_to_bot = (message.reply_to_message and 
                          message.reply_to_message.from_user and 
                          message.reply_to_message.from_user.id == bot_id)
        is_tagged = bot_username in message_text

        if is_tagged or is_reply_to_bot:
            # Получаем контекст с учетом всей истории группы
            group_context = await self.context_manager.get_context(chat_id)
            
            # Формируем запрос для AI
            if is_tagged:
                query = message_text.replace(bot_username, "").strip()
                ai_prompt = f"Тебя упомянули в группе. Ответь на вопрос: {query}\n\nВот контекст последних сообщений:\n{group_context}"
            else:
                ai_prompt = f"Тебе ответили на сообщение. Вот новое сообщение: {message_text}\n\nВот контекст последних сообщений:\n{group_context}"
            
            # Получаем ответ от AI
            ai_response = await AiHandler.get_ai_response([], ai_prompt)
            
            # Отправляем ответ
            sent_message = await message.reply(ai_response)
            await self.save_chat_message(chat_id, bot_id, sent_message.message_id, "assistant", ai_response)
        
        # Обработка случайного вмешательства
        elif should_intervene:
            group_context = await self.context_manager.get_context(chat_id)
            ai_prompt = f"Ты читаешь групповой чат и хочешь вмешаться. Вот последние сообщения:\n{group_context}\n\nНапиши короткое сообщение для вмешательства в разговор, максимум 1-2 предложения."
            
            ai_response = await AiHandler.get_ai_response([], ai_prompt)
            sent_message = await message.reply(ai_response)
            await self.save_chat_message(chat_id, bot_id, sent_message.message_id, "assistant", ai_response)
            
            # Обновляем время последнего сообщения бота
            self.context_manager.last_bot_message_time[chat_id] = time.time()
    
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)

    def setup_handlers(self):
        self.dp.message.register(self.command_start, Command("start"))
        self.dp.message.register(self.command_version, Command("version"))
        self.dp.message.register(self.command_reset, Command("reset"))
        self.dp.message.register(partial(self.command_team_matches, team_name="real"), Command("real"))
        self.dp.message.register(partial(self.command_team_matches, team_name="lfc"), Command("lfc"))
        self.dp.message.register(partial(self.command_team_matches, team_name="arsenal"), Command("arsenal"))
        self.dp.message.register(self.handle_message)

    async def start(self):
        self.setup_handlers()
        await self.on_startup()
        try:
            await self.dp.start_polling(self.bot, allowed_updates=["message"])
        finally:
            await self.on_shutdown()

async def main():
    bot_app = BotApp()
    try:
        logger.info("Запуск бота...")
        await bot_app.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Необработанная ошибка в main: {e}")

if __name__ == "__main__":
    print(f"Старт приложения. Версия: {CODE_VERSION}")
    asyncio.run(main())
