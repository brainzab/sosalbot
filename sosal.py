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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Версия кода
CODE_VERSION = "2.6"

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

# Настройка клиента DeepSeek
deepseek_client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Константы для ответов
RESPONSES_SOSAL = ['да', 'было', 'ну сосал', 'прям ща']
RARE_RESPONSE_SOSAL = 'пошел нахуй'
RESPONSE_LETAL = 'да'
RESPONSES_SCAMIL = ['да', 'было', 'с кайфом']

# ID пользователя для реакции
TARGET_USER_ID = 660949286
TARGET_REACTION = ReactionTypeEmoji(emoji="😁")

# ID команд для API-Football
TEAM_IDS = {
    "real": 541,  # Real Madrid
    "lfc": 40,    # Liverpool
    "arsenal": 42 # Arsenal
}

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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            logger.error(f"Исключение при получении цен криптовалют: {e}")
            return 0, 0

    @staticmethod
    async def get_team_matches(team_id):
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures?team={team_id}&last=5"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.error(f"Ошибка API-Football для команды {team_id}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Исключение при запросе матчей: {e}")
            return None

    @staticmethod
    async def get_match_events(fixture_id):
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/events?fixture={fixture_id}"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"События для матча {fixture_id}: {data}")
                        return data
                    logger.error(f"Ошибка API-Football для событий матча {fixture_id}: {response.status}")
                    return None
        except Exception as e:
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
                max_tokens=999,
                temperature=1.5
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
            cities = {
                "Минск": "Minsk,BY",
                "Жлобин": "Zhlobin,BY",
                "Гомель": "Gomel,BY",
                "Житковичи": "Zhitkovichi,BY",
                "Шри-Ланка": "Colombo,LK",
                "Ноябрьск": "Noyabrsk,RU"
            }
            
            weather_data = {}
            for city_name, city_code in cities.items():
                weather_data[city_name] = await ApiClient.get_weather(city_code)
            
            usd_byn_rate, usd_rub_rate = await ApiClient.get_currency_rates()
            btc_price_usd, wld_price_usd = await ApiClient.get_crypto_prices()
            
            try:
                btc_price_byn = float(btc_price_usd) * float(usd_byn_rate) if btc_price_usd and usd_byn_rate else 0
                wld_price_byn = float(wld_price_usd) * float(usd_byn_rate) if wld_price_usd and usd_byn_rate else 0
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка конвертации курсов: {e}")
                btc_price_byn = wld_price_byn = 0

            message = (
                "Родные мои, всем доброе утро и хорошего дня! ❤️\n\n"
                "*Положняк по погоде:*\n"
                f"🌥 *Минск*: {weather_data['Минск']}\n"
                f"🌥 *Жлобин*: {weather_data['Жлобин']}\n"
                f"🌥 *Гомель*: {weather_data['Гомель']}\n"
                f"🌥 *Житковичи*: {weather_data['Житковичи']}\n"
                f"🌴 *Шри-Ланка*: {weather_data['Шри-Ланка']}\n"
                f"❄️ *Ноябрьск*: {weather_data['Ноябрьск']}\n\n"
                "*Положняк по курсам:*\n"
            )
            
            if usd_byn_rate:
                message += f"💵 *USD/BYN*: {usd_byn_rate:.2f} BYN\n"
            if usd_rub_rate:
                message += f"💵 *USD/RUB*: {usd_rub_rate:.2f} RUB\n"
            if btc_price_usd:
                message += f"₿ *BTC*: ${btc_price_usd:,.2f} USD | {btc_price_byn:,.2f} BYN\n" if btc_price_byn else f"₿ *BTC*: ${btc_price_usd:,.2f} USD\n"
            if wld_price_usd:
                message += f"🌍 *WLD*: ${wld_price_usd:.2f} USD | {wld_price_byn:.2f} BYN\n" if wld_price_byn else f"🌍 *WLD*: ${wld_price_usd:.2f} USD\n"
            
            await self.bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode=types.ParseMode.MARKDOWN
            )
            logger.info("Утреннее сообщение отправлено")
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего сообщения: {e}")

# Основной класс бота
class BotApp:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.dp = Dispatcher()
        self.scheduler = None
        self.morning_sender = None
        self.keep_alive_task = None
        self.chat_histories = {}

    async def keep_alive(self):
        while True:
            logger.info("Бот активен")
            await asyncio.sleep(300)

    async def on_startup(self):
        logger.info(f"Запуск бота версии {CODE_VERSION}")
        self.morning_sender = MorningMessageSender(self.bot)
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        self.scheduler.add_job(
            self.morning_sender.send_morning_message,
            trigger=CronTrigger(hour=17, minute=50)
        )
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
        await self.bot.session.close()
        logger.info("Бот остановлен")

    @staticmethod
    async def command_start(message: types.Message):
        await message.reply(f"Привет, я бот версии {CODE_VERSION}")

    @staticmethod
    async def command_version(message: types.Message):
        await message.reply(f"Версия бота: {CODE_VERSION}")

    async def command_reset(self, message: types.Message):
        chat_id = message.chat.id
        if chat_id in self.chat_histories:
            del self.chat_histories[chat_id]
            await message.reply("История чата сброшена, мудила. Начинаем с чистого листа!")
        else:
            await message.reply("А хули сбрасывать? И так пусто, как в голове у тебя!")

    async def command_team_matches(self, message: types.Message, team_name):
        team_id = TEAM_IDS.get(team_name)
        if not team_id:
            await message.reply("Команда не найдена, мудила!")
            return

        data = await ApiClient.get_team_matches(team_id)
        if not data or not data.get("response"):
            await message.reply("Не удалось получить данные о матчах. Пиздец какой-то!")
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

        await message.reply(response)

    async def handle_message(self, message: types.Message):
        try:
            if not message.from_user or not message.text:
                return

            message_text = message.text.lower()
            bot_info = await self.bot.get_me()
            bot_username = f"@{bot_info.username.lower()}"
            bot_id = bot_info.id

            logger.info(f"Сообщение от {message.from_user.id}: {message.text}")

            if message.from_user.id == TARGET_USER_ID:
                try:
                    await self.bot.set_message_reaction(
                        chat_id=message.chat_id,
                        message_id=message.message_id,
                        reaction=[TARGET_REACTION]
                    )
                except Exception as e:
                    logger.error(f"Ошибка при установке реакции: {e}")

            is_reply_to_bot = (message.reply_to_message and 
                              message.reply_to_message.from_user and 
                              message.reply_to_message.from_user.id == bot_id)
            is_tagged = bot_username in message_text

            if message_text in ['сосал?', 'sosal?']:
                response = RARE_RESPONSE_SOSAL if random.random() < 0.1 else random.choice(RESPONSES_SOSAL)
                await message.reply(response)
            elif message_text == 'летал?':
                await message.reply(RESPONSE_LETAL)
            elif message_text == 'скамил?':
                await message.reply(random.choice(RESPONSES_SCAMIL))
            elif is_tagged or is_reply_to_bot:
                query = message_text.replace(bot_username, "").strip() if is_tagged else message_text
                
                if not query:
                    await message.reply("И хуле ты мне пишешь пустоту, петушара?")
                    return
                
                chat_id = message.chat.id
                if chat_id not in self.chat_histories:
                    self.chat_histories[chat_id] = []
                
                chat_history = self.chat_histories[chat_id]
                if is_reply_to_bot and message.reply_to_message.text:
                    chat_history = chat_history + [{"role": "assistant", "content": message.reply_to_message.text}]
                
                ai_response = await AiHandler.get_ai_response(chat_history, query)
                
                self.chat_histories[chat_id].append({"role": "user", "content": query})
                self.chat_histories[chat_id].append({"role": "assistant", "content": ai_response})
                
                if len(self.chat_histories[chat_id]) > 30:
                    self.chat_histories[chat_id] = self.chat_histories[chat_id][-30:]
                
                await message.reply(ai_response)
        except Exception as e:
            logger.error(f"Ошибка в обработке сообщения: {e}")

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

# Запуск приложения
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
