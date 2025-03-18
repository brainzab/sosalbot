import random
import os
from telegram.ext import Application, MessageHandler, filters
from openai import OpenAI

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

# Асинхронная функция обработки сообщений
async def handle_message(update, context):
    message_text = update.message.text.lower()
    bot_username = f"@{context.bot.username.lower()}"  # Получаем имя бота (например, @YourBotName)

    # Реакция на "сосал?" или "sosal?"
    if message_text in ['сосал?', 'sosal?']:
        if random.random() < 0.1:  # 10% шанс
            await update.message.reply_text(RARE_RESPONSE_SOSAL)
        else:
            random_response = random.choice(RESPONSES_SOSAL)
            await update.message.reply_text(random_response)
    
    # Реакция на "летал?"
    elif message_text == 'летал?':
        await update.message.reply_text(RESPONSE_LETAL)
    
    # Реакция на "скамил?"
    elif message_text == 'скамил?':
        random_response = random.choice(RESPONSES_SCAMIL)
        await update.message.reply_text(random_response)
    
    # Реакция только на сообщения с упоминанием бота (например, @YourBotName)
    elif bot_username in message_text:
        # Убираем имя бота из текста для обработки DeepSeek
        query = message_text.replace(bot_username, "").strip()
        if not query:  # Если после удаления тега ничего не осталось
            await update.message.reply_text("Что ты хочешь узнать?")
            return
        
        try:
            # Отправляем запрос к DeepSeek API
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Ты полезный ИИ-агент в Telegram-группе. Отвечай кратко и по делу."},
                    {"role": "user", "content": query}
                ],
                max_tokens=500,
                temperature=0.7
            )
            ai_response = response.choices[0].message.content
            await update.message.reply_text(ai_response)
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {str(e)}")

def main():
    # Создаем объект Application для Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).read_timeout(30).build()
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
