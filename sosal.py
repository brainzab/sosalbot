import random
from telegram.ext import Application, MessageHandler, filters
import os

# Токен берется из переменной окружения для безопасности
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Список возможных ответов для "сосал?" и "sosal?"
RESPONSES_SOSAL = ['да', 'было', 'ну сосал', 'прям ща']

# Редкий ответ для "сосал?" и "sosal?" (10% шанс)
RARE_RESPONSE_SOSAL = 'пошел нахуй'

# Ответ для "летал?"
RESPONSE_LETAL = 'да'

# Список возможных ответов для "скамил?"
RESPONSES_SCAMIL = ['да', 'было', 'с кайфом']

# Асинхронная функция обработки сообщений
async def handle_message(update, context):
    message_text = update.message.text.lower()
    
    # Реакция на "сосал?" или "sosal?"
    if message_text in ['сосал?', 'sosal?']:
        # Генерируем случайное число от 0 до 1
        if random.random() < 0.1:  # 10% шанс
            await update.message.reply_text(RARE_RESPONSE_SOSAL)
        else:  # 90% шанс
            random_response = random.choice(RESPONSES_SOSAL)
            await update.message.reply_text(random_response)
    
    # Реакция на "летал?"
    elif message_text == 'летал?':
        await update.message.reply_text(RESPONSE_LETAL)
    
    # Реакция на "скамил?"
    elif message_text == 'скамил?':
        random_response = random.choice(RESPONSES_SCAMIL)
        await update.message.reply_text(random_response)

def main():
    # Создаем объект Application с увеличенным временем ожидания
    application = Application.builder().token(TOKEN).read_timeout(30).build()
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
