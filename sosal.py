import random
import os
from telegram.ext import Application, MessageHandler, filters
from openai import OpenAI
from datetime import datetime

# Токен Telegram бота и API-ключ DeepSeek из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

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
TARGET_USER_ID = 660949286  # Замените на реальный ID
TARGET_REACTION = [{"type": "emoji", "emoji": "😁"}]

# Асинхронная функция обработки сообщений
async def handle_message(update, context):
    message = update.message
    message_text = message.text.lower()
    bot_username = f"@{context.bot.username.lower()}"

    # Реакция на сообщения целевого пользователя
    if message.from_user.id == TARGET_USER_ID:
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=TARGET_REACTION
            )
        except Exception as e:
            print(f"Ошибка при установке реакции: {e}")

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
    elif bot_username in message_text:
        query = message_text.replace(bot_username, "").strip()
        if not query:
            await message.reply_text("И хуле ты меня тегнул, петушара?")
            return
        
        # Проверяем запросы о дате
        current_year = datetime.now().year
        if "год" in query or "сейчас" in query or "дата" in query:
            await message.reply_text(f"Сейчас {current_year} год, хуеглот. Чё, календарь потерял?")
            return
        
        try:
            # Отправляем запрос к DeepSeek API с новым промптом
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

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).read_timeout(30).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
