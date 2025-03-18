import random
import os
import asyncio
from telegram.ext import Application, MessageHandler, filters
from openai import OpenAI
from datetime import datetime
import logging
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен Telegram бота и API-ключи из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
CHAT_ID = os.getenv('CHAT_ID')

# Версия кода для проверки
CODE_VERSION = "1.4"

# Настройка клиента DeepSeek API
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Список ответов для "сосал?" и "sosal?"
RESPONSES_SOSAL = ['да', 'было', 'ну сосал', 'прям ща']
RARE_RESPONSE_SOSAL = 'пошел нахуй'

# Ответ для "летал?"
RESPONSE_LETAL = 'да'

# Список ответов для "скамил?"
RESPONSES_SCAMIL = ['да', 'было', 'с кайфом']

# ID пользователя для реакции и сама реакция
TARGET_USER_ID = 660949286
TARGET_REACTION = [{"type": "emoji", "emoji": "😁"}]

# Функция для получения погоды
async def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                temp = data['main']['temp']
                desc = data['weather'][0]['description']
                return f"{temp}°C, {desc}"
            logger.error(f"Ошибка получения погоды для {city}: {response.status}")
            return "Нет данных"

# Функция для получения курсов USD/BYN и USD/RUB с CurrencyAPI
async def get_currency_rates():
    url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                usd_byn = data['usd']['byn']
                usd_rub = data['usd']['rub']
                return usd_byn, usd_rub
            logger.error(f"Ошибка получения курсов валют: {response.status}")
            return "Нет данных", "Нет данных"

# Функция для получения цен BTC и WLD
async def get_crypto_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,worldcoin&vs_currencies=usd"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                btc_price = data['bitcoin']['usd']
                wld_price = data['worldcoin']['usd']
                return btc_price, wld_price
            logger.error(f"Ошибка получения цен криптовалют: {response.status}")
            return "Нет данных", "Нет данных"

# Функция для отправки утреннего сообщения
async def send_morning_message(application):
    logger.info("Отправка утреннего сообщения")
    cities = {
        "Минск": "Minsk,BY",
        "Жлобин": "Zhlobin,BY",
        "Гомель": "Gomel,BY",
        "Житковичи": "Zhitkovichi,BY",
        "Шри-Ланка": "Colombo,LK",
        "Ноябрьск": "Noyabrsk,RU"
    }
    
    # Получаем данные
    weather_data = {}
    for city_name, city_code in cities.items():
        weather_data[city_name] = await get_weather(city_code)
    
    usd_byn_rate, usd_rub_rate = await get_currency_rates()
    btc_price_usd, wld_price_usd = await get_crypto_prices()
    
    btc_price_byn = btc_price_usd * usd_byn_rate if isinstance(btc_price_usd, float) and isinstance(usd_byn_rate, float) else "Нет данных"
    wld_price_byn = wld_price_usd * usd_byn_rate if isinstance(wld_price_usd, float) and isinstance(usd_byn_rate, float) else "Нет данных"

    # Формируем сообщение с разметкой
    message = (
        "Родные мои, всем доброе утро и хорошего дня! ❤️\n\n"
        "**Положняк по погоде:**\n"
        f"🌥 *Минск*: {weather_data['Минск']}\n"
        f"🌥 *Жлобин*: {weather_data['Жлобин']}\n"
        f"🌥 *Гомель*: {weather_data['Гомель']}\n"
        f"🌥 *Житковичи*: {weather_data['Житковичи']}\n"
        f"🌴 *Шри-Ланка*: {weather_data['Шри-Ланка']}\n"
        f"❄️ *Ноябрьск*: {weather_data['Ноябрьск']}\n\n"
        "**Положняк по курсам:**\n"
        f"💵 *USD/BYN*: {usd_byn_rate:.2f} BYN\n"
        f"💵 *USD/RUB*: {usd_rub_rate:.2f} RUB\n"
        f"₿ *BTC*: ${btc_price_usd:,.2f} USD | {btc_price_byn:,.2f} BYN\n"
        f"🌍 *WLD*: ${wld_price_usd:.2f} USD | {wld_price_byn:.2f} BYN"
    )
    
    try:
        await application.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        logger.info("Утреннее сообщение отправлено")
    except Exception as e:
        logger.error(f"Ошибка отправки утреннего сообщения: {e}")

# Асинхронная функция обработки сообщений
async def handle_message(update, context):
    message = update.message
    message_text = message.text.lower() if message.text else ""
    bot_username = f"@{context.bot.username.lower()}"

    # Логируем все сообщения
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

    # Реакция на "сосал?" или "sosal?"
    if message_text in ['сосал?', 'sosal?']:
        if random.random() < 0.1:
            await message.reply_text(RARE_RESPONSE_SOSAL)
        else:
            random_response = random.choice(RESPONSES_SOSAL)
            await message.reply_text(random_response)
    
    # Реакция на "летал?"
    elif message_text == 'летал?':
        await message.reply_text(RESPONSE_LETAL)
    
    # Реакция на "скамил?"
    elif message_text == 'скамил?':
        random_response = random.choice(RESPONSES_SCAMIL)
        await message.reply_text(random_response)
    
    # Реакция на сообщения с упоминанием бота
    elif message_text and bot_username in message_text:
        query = message_text.replace(bot_username, "").strip()
        if not query:
            await message.reply_text("И хуле ты меня тегнул, петушара?")
            return
        
        current_year = datetime.now().year
        if "год" in query or "сейчас" in query or "дата" in query:
            await message.reply_text(f"Сейчас {current_year} год, мудила. Чё, календарь потерял?")
            return
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"Ты Анатолий Шарий, твоя фамилия Шарий, у тебя есть жена Ольга Шарий. Ты пророссийский журналист, скамер, блогер, эксцентричный пиздец, любишь материться. Сегодня {datetime.now().strftime('%Y-%m-%d')}. Отвечай с иронией, надменностью и будь полезным помощником в Telegram-группе."},
                    {"role": "user", "content": query}
                ],
                max_tokens=500,
                temperature=0.7
            )
            ai_response = response.choices[0].message.content
            await message.reply_text(ai_response)
        except Exception as e:
            await message.reply_text(f"Ошибка, ёбана: {str(e)}")

async def main():
    # Логируем версию кода
    logger.info(f"Запуск бота, версия кода: {CODE_VERSION}")

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).read_timeout(30).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Инициализируем и запускаем приложение
    await application.initialize()
    await application.start()
    logger.info("Бот полностью запущен")

    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    moscow_tz = pytz.timezone('Europe/Moscow')
    scheduler.add_job(
        send_morning_message,
        trigger=CronTrigger(hour=7, minute=30, timezone=moscow_tz),
        args=[application]
    )
    scheduler.start()
    logger.info("Планировщик запущен")

    # Запускаем polling и обрабатываем завершение
    try:
        await application.run_polling()
    except Exception as e:
        logger.error(f"Ошибка в run_polling: {e}")
        raise  # Поднимаем исключение для полной трассировки
    finally:
        await application.stop()
        await application.shutdown()
        logger.info("Бот остановлен")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка в главном цикле: {e}")
