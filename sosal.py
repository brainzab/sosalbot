import random
import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler as TelegramMessageHandler, filters
from telegram.constants import ParseMode
from openai import AsyncOpenAI
import aiohttp
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Версия кода
CODE_VERSION = "2.1"

# Получение переменных окружения
def get_env_var(var_name, default=None):
    value = os.getenv(var_name)
    if value is None and default is None:
        logger.error(f"Отсутствует обязательная переменная окружения: {var_name}")
        sys.exit(1)
    return value if value is not None else default

# Токен Telegram бота и API-ключи
TELEGRAM_TOKEN = get_env_var('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = get_env_var('DEEPSEEK_API_KEY')
OPENWEATHER_API_KEY = get_env_var('OPENWEATHER_API_KEY')
CHAT_ID = get_env_var('CHAT_ID')

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
TARGET_REACTION = [{"type": "emoji", "emoji": "😁"}]

# Класс для всех API-запросов
class ApiClient:
    @staticmethod
    async def get_weather(city):
        """Получение погоды из OpenWeatherMap"""
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        temp = data['main']['temp']
                        desc = data['weather'][0]['description']
                        return f"{temp}°C, {desc}"
                    else:
                        logger.error(f"Ошибка получения погоды для {city}: {response.status}")
                        return "Нет данных"
        except Exception as e:
            logger.error(f"Исключение при получении погоды: {e}")
            return "Нет данных"

    @staticmethod
    async def get_currency_rates():
        """Получение курсов валют"""
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        usd_byn = data['usd'].get('byn', 0)
                        usd_rub = data['usd'].get('rub', 0)
                        return usd_byn, usd_rub
                    else:
                        logger.error(f"Ошибка получения курсов валют: {response.status}")
                        return 0, 0
        except Exception as e:
            logger.error(f"Исключение при получении курсов валют: {e}")
            return 0, 0

    @staticmethod
    async def get_crypto_prices():
        """Получение цен на криптовалюты"""
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,worldcoin&vs_currencies=usd"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        btc_price = data.get('bitcoin', {}).get('usd', 0)
                        wld_price = data.get('worldcoin', {}).get('usd', 0)
                        return btc_price, wld_price
                    else:
                        logger.error(f"Ошибка получения цен криптовалют: {response.status}")
                        return 0, 0
        except Exception as e:
            logger.error(f"Исключение при получении цен криптовалют: {e}")
            return 0, 0

# Класс для работы с AI
class AiHandler:
    @staticmethod
    async def get_ai_response(query):
        """Получение ответа от DeepSeek AI"""
        try:
            response = await deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"Ты Анатолий Шарий, твоя фамилия Шарий, у тебя есть жена Ольга Шарий. Ты пророссийский журналист, скамер, блогер, эксцентричный пиздец, любишь материться. Сегодня {datetime.now().strftime('%Y-%m-%d')}. Отвечай с иронией, надменностью и будь полезным помощником в Telegram-группе."},
                    {"role": "user", "content": query}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            return f"Ошибка, ёбана: {str(e)}"

# Класс для обработки команд и сообщений (переименован, чтобы избежать конфликта)
class BotMessageHandler:
    def __init__(self, application):
        self.application = application

    async def handle_message(self, update: Update, context):
        """Обработка входящих сообщений"""
        try:
            message = update.message
            if not message or not message.from_user:
                return

            message_text = message.text.lower() if message.text else ""
            bot_username = f"@{context.bot.username.lower()}" if context.bot and context.bot.username else ""

            # Логирование сообщений
            logger.info(f"Сообщение от {message.from_user.id}: {message.text or 'Без текста'}")

            # Реакция на сообщения целевого пользователя
            if message.from_user.id == TARGET_USER_ID:
                try:
                    await context.bot.set_message_reaction(
                        chat_id=message.chat_id,
                        message_id=message.message_id,
                        reaction=TARGET_REACTION
                    )
                except Exception as e:
                    logger.error(f"Ошибка при установке реакции: {e}")

            # Обработка специальных сообщений
            if message_text in ['сосал?', 'sosal?']:
                if random.random() < 0.1:
                    await message.reply_text(RARE_RESPONSE_SOSAL)
                else:
                    random_response = random.choice(RESPONSES_SOSAL)
                    await message.reply_text(random_response)
            elif message_text == 'летал?':
                await message.reply_text(RESPONSE_LETAL)
            elif message_text == 'скамил?':
                random_response = random.choice(RESPONSES_SCAMIL)
                await message.reply_text(random_response)
            # Обработка сообщений с упоминанием бота
            elif message_text and bot_username and bot_username in message_text:
                query = message_text.replace(bot_username, "").strip()
                if not query:
                    await message.reply_text("И хуле ты меня тегнул, петушара?")
                    return
                
                # Проверка на специальные запросы
                current_year = datetime.now().year
                if "год" in query or "сейчас" in query or "дата" in query:
                    await message.reply_text(f"Сейчас {current_year} год, мудила. Чё, календарь потерял?")
                    return
                
                # Получение ответа от AI
                ai_response = await AiHandler.get_ai_response(query)
                await message.reply_text(ai_response)
        except Exception as e:
            logger.error(f"Ошибка в обработке сообщения: {e}")

    async def command_start(self, update: Update, context):
        """Обработка команды /start"""
        await update.message.reply_text("Привет, я бот версии " + CODE_VERSION)

    async def command_version(self, update: Update, context):
        """Обработка команды /version"""
        await update.message.reply_text(f"Версия бота: {CODE_VERSION}")

# Класс для отправки утренних сообщений
class MorningMessageSender:
    def __init__(self, application):
        self.application = application

    async def send_morning_message(self):
        """Отправка утреннего сообщения"""
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
            
            # Получаем данные по погоде
            weather_data = {}
            for city_name, city_code in cities.items():
                weather_data[city_name] = await ApiClient.get_weather(city_code)
            
            # Получаем данные по курсам и криптовалютам
            usd_byn_rate, usd_rub_rate = await ApiClient.get_currency_rates()
            btc_price_usd, wld_price_usd = await ApiClient.get_crypto_prices()
            
            # Расчет стоимости в BYN
            try:
                btc_price_byn = float(btc_price_usd) * float(usd_byn_rate) if btc_price_usd and usd_byn_rate else 0
                wld_price_byn = float(wld_price_usd) * float(usd_byn_rate) if wld_price_usd and usd_byn_rate else 0
            except (ValueError, TypeError):
                btc_price_byn = 0
                wld_price_byn = 0

            # Формируем сообщение
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
            
            # Добавляем курсы валют и криптовалют, если они доступны
            if usd_byn_rate:
                message += f"💵 *USD/BYN*: {usd_byn_rate:.2f} BYN\n"
            if usd_rub_rate:
                message += f"💵 *USD/RUB*: {usd_rub_rate:.2f} RUB\n"
            if btc_price_usd:
                message += f"₿ *BTC*: ${btc_price_usd:,.2f} USD"
                if btc_price_byn:
                    message += f" | {btc_price_byn:,.2f} BYN"
                message += "\n"
            if wld_price_usd:
                message += f"🌍 *WLD*: ${wld_price_usd:.2f} USD"
                if wld_price_byn:
                    message += f" | {wld_price_byn:.2f} BYN"
                message += "\n"
            
            # Отправляем сообщение
            await self.application.bot.send_message(
                chat_id=CHAT_ID, 
                text=message, 
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info("Утреннее сообщение отправлено")
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего сообщения: {e}")

# Класс для управления приложением бота
class BotApp:
    def __init__(self):
        self.application = None
        self.scheduler = None
        self.message_handler = None
        self.morning_sender = None
        self.keep_alive_task = None

    async def keep_alive(self):
        """Функция для поддержания активности приложения"""
        while True:
            logger.info("Бот активен")
            await asyncio.sleep(300)  # Каждые 5 минут

    async def start(self):
        """Запуск бота"""
        try:
            logger.info(f"Запуск бота версии {CODE_VERSION}")
            
            # Создаем экземпляр приложения
            self.application = Application.builder().token(TELEGRAM_TOKEN).build()
            
            # Создаем экземпляры обработчиков
            self.message_handler = BotMessageHandler(self.application)
            self.morning_sender = MorningMessageSender(self.application)
            
            # Регистрируем обработчики
            self.application.add_handler(CommandHandler("start", self.message_handler.command_start))
            self.application.add_handler(CommandHandler("version", self.message_handler.command_version))
            self.application.add_handler(TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler.handle_message))
            
            # Создаем и запускаем планировщик
            self.scheduler = AsyncIOScheduler()
            moscow_tz = pytz.timezone('Europe/Moscow')
            self.scheduler.add_job(
                self.morning_sender.send_morning_message,
                trigger=CronTrigger(hour=7, minute=30, timezone=moscow_tz)
            )
            self.scheduler.start()
            logger.info("Планировщик запущен")
            
            # Запускаем задачу для поддержания активности
            self.keep_alive_task = asyncio.create_task(self.keep_alive())
            
            # Запускаем бота
            await self.application.initialize()
            await self.application.start()
            logger.info("Бот успешно запущен")
            
            # Запускаем polling
            await self.application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise

    async def stop(self):
        """Остановка бота"""
        try:
            logger.info("Остановка бота")
            
            # Останавливаем задачу поддержания активности
            if self.keep_alive_task and not self.keep_alive_task.done():
                self.keep_alive_task.cancel()
                try:
                    await self.keep_alive_task
                except asyncio.CancelledError:
                    pass
            
            # Останавливаем планировщик
            if self.scheduler:
                self.scheduler.shutdown()
                logger.info("Планировщик остановлен")
            
            # Останавливаем приложение
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
                logger.info("Приложение остановлено")
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")
            raise

# Основная функция
async def main():
    bot = BotApp()
    try:
        logger.info("Запуск бота...")
        await bot.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.stop()
        logger.info("Бот остановлен")

# Запуск приложения
if __name__ == "__main__":
    print(f"Старт приложения. Версия: {CODE_VERSION}")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Программа завершена по запросу пользователя")
    except Exception as e:
        print(f"Необработанная ошибка: {e}")
