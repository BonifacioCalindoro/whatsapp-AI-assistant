from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from httpx import AsyncClient
import os
from dotenv import load_dotenv
import logging
import random
import pickle

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

def load_thought_messages():
    if os.path.exists('thought_messages.pkl'):
        return pickle.load(open('thought_messages.pkl', 'rb'))
    else:
        return {}

thought_messages = load_thought_messages()

def save_thought_messages():
    pickle.dump(thought_messages, open('thought_messages.pkl', 'wb'))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("Yes")


async def chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(update.effective_chat.id)

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global thought_messages
    query = update.callback_query
    s, chat_id, message_id = query.data.split('_')
    if s == 'complete':
        await query.answer('Completando...')
        message = await update.effective_chat.send_message('<i>Completando...</i>', parse_mode='HTML')
        async with AsyncClient(timeout=120) as client:
            response = await client.post('http://localhost:47549/complete', json={
                'chatId': chat_id,
                'messageId': message_id
            })
        response = response.json()["message"].replace('Usuario 1: ', '').replace('Usuario 2: ', '')
        if chat_id not in thought_messages.keys():
            thought_messages[chat_id] = {}
        response_id = str(random.randint(0, 1000000))
        thought_messages[chat_id][response_id] = response
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('Enviar', callback_data=f'send_{chat_id}_{response_id}')]])
        await message.edit_text(f'<code>{response}</code>', parse_mode='HTML', reply_markup=keyboard)
        save_thought_messages()
        
    elif s == 'send':
        pickle.dump({
            'telephone': chat_id,
            'message': thought_messages[chat_id][message_id],
            'filename': f'{chat_id}_{message_id}.pkl'
        }, open(f'sendable_messages/{chat_id}_{message_id}.pkl', 'wb'))
        await query.answer('Puesto en cola')

def main():
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    application.add_handler(CommandHandler('start', start, block=False))
    application.add_handler(CallbackQueryHandler(callback_query, block=False))
    application.run_polling()

if __name__ == '__main__':
    main()