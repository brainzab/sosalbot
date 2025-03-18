import random
import os
import asyncio
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI
from datetime import datetime
import logging
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from telegram import Update

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
CHAT_ID = os.getenv('CHAT_ID')

# Version control
CODE_VERSION = "1.3"

# Initialize DeepSeek API client
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Predefined responses
RESPONSES_SOSAL = ['да', 'было', 'ну сосал', 'прям ща']
RARE_RESPONSE_SOSAL = 'пошел нахуй'
RESPONSE_LETAL = 'да'
RESPONSES_SCAMIL = ['да', 'было', 'с кайфом']
TARGET_USER_ID = 660949286
TARGET_REACTION = [{"type": "emoji", "emoji": "😁"}]

async def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                temp = data['main']['temp']
                desc = data['weather'][0]['description']
                return f"{temp}°C, {desc}"
            return "Нет данных"

async def get_currency_rates():
    url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                usd_byn = data['usd']['byn']
                usd_rub = data['usd']['rub']
                return usd_byn, usd_rub
            return "Нет данных", "Нет данных"

async def get_crypto_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,worldcoin&vs_currencies=usd"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                btc_price = data['bitcoin']['usd']
                wld_price = data['worldcoin']['usd']
                return btc_price, wld_price
            return "Нет данных", "Нет данных"

async def send_morning_message(application):
    logger.info("Sending morning message")
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
        weather_data[city_name] = await get_weather(city_code)

    usd_byn_rate, usd_rub_rate = await get_currency_rates()
    btc_price_usd, wld_price_usd = await get_crypto_prices()

    btc_price_byn = btc_price_usd * usd_byn_rate if isinstance(btc_price_usd, float) and isinstance(usd_byn_rate, float) else "Нет данных"
    wld_price_byn = wld_price_usd * usd_byn_rate if isinstance(wld_price_usd, float) and isinstance(usd_byn_rate, float) else "Нет данных"

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

    await application.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    logger.info("Morning message sent")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    message_text = message.text.lower() if message.text else ""
    bot_username = f"@{context.bot.username.lower()}"

    logger.info(f"Message from {message.from_user.id}: {message.text or 'No text'}")

    if message.from_user.id == TARGET_USER_ID:
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=TARGET_REACTION
            )
        except Exception as e:
            logger.error(f"Error setting reaction: {e}")

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
    logger.info(f"Starting bot, version: {CODE_VERSION}")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.initialize()
    await application.start()
    logger.info("Bot fully started")

    scheduler = AsyncIOScheduler()
    moscow_tz = pytz.timezone('Europe/Moscow')
    scheduler.add_job(
        send_morning_message,
        trigger=CronTrigger(hour=7, minute=30, timezone=moscow_tz),
        args=[application]
    )
    scheduler.start()

    try:
        await application.run_polling(allowed_updates=Update)
    except Exception as e:
        logger.error(f"Error in run_polling: {e}")
    finally:
        await application.stop()
        await application.shutdown()
        logger.info("Bot stopped")

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        loop.close()
