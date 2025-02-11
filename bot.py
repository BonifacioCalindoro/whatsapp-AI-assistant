from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from httpx import AsyncClient
import os
from elevenlabs.types import VoiceSettings
from dotenv import load_dotenv
import logging
import random
import pickle
from utils import text_to_speech, edit_voice_settings, delete_voice
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

voice_id = os.getenv('ELEVENLABS_VOICE_ID')

if not os.path.exists('sendable_messages'):
    os.makedirs('sendable_messages')

def load_thought_messages():
    if os.path.exists('thought_messages.pkl'):
        return pickle.load(open('thought_messages.pkl', 'rb'))
    else:
        return {}

thought_messages = load_thought_messages()

def save_thought_messages():
    pickle.dump(thought_messages, open('thought_messages.pkl', 'wb'))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yes, I'm alive!")

async def clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telephones = [tel.replace('.pkl', '') for tel in os.listdir('samples') if tel.endswith('.pkl')]
    keyboard = [InlineKeyboardButton(tel, callback_data=f'clone_choice_{tel}') for tel in telephones]
    reply_markup = InlineKeyboardMarkup([keyboard])
    await update.message.reply_text("Choose a telephone to clone:", reply_markup=reply_markup)
    return 'choose_telephone'

async def choose_telephone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')[-1]
    await query.answer()
    context.user_data['telephone'] = data
    message = await update.effective_chat.send_message(f'Set a name for the new voice:', parse_mode='HTML')
    return 'set_name'

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.effective_message.text
    await update.effective_chat.send_message(f'Set a description for the new voice:', parse_mode='HTML')
    return 'set_description'

async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.effective_message.text
    await update.effective_chat.send_message(f'Cloning...')
    async with AsyncClient(timeout=120) as client:
        response = await client.post('http://localhost:47549/clone', json={
            'telephone': context.user_data['telephone'],
            'name': context.user_data['name'],
            'prompt': context.user_data['description']
        })
        response = response.json()
        if response['error']:
            await update.effective_chat.send_message(f'Error: {response["message"]}')
            return ConversationHandler.END
        else:
            voices, voice = response['voices'], response['voice']
            await update.effective_chat.send_message(f'Voice <code>{voice["voice_id"]}</code> cloned successfully!', parse_mode='HTML')
    return ConversationHandler.END

async def get_voices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with AsyncClient(timeout=120) as client:
        response = await client.get('http://localhost:47549/voices')
        response = response.json()
    voices = response['voices']
    await update.effective_chat.send_message(f'Voices:')
    msg = ''
    for v in voices:
        msg += f'<code>{v["voice_id"]}</code>: {v["name"]}\n'
    await update.effective_chat.send_message(msg, parse_mode='HTML')

async def set_voice_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global voice_id
    id = update.effective_message.text.replace('/setvoiceid ', '')
    async with AsyncClient(timeout=120) as client:
        response = await client.get('http://localhost:47549/voices')
        response = response.json()
        voices = response['voices']
    print(voices)
    if id in [v['voice_id'] for v in voices]:
        voice_id = id
        await update.effective_chat.send_message(f'Voice ID set to <code>{voice_id}</code>', parse_mode='HTML')
    else:
        await update.effective_chat.send_message(f'Voice ID not found')

async def edit_voice_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        voice_id, stability, similarity_boost, style, use_speaker_boost = context.args
        stability = float(stability)
        similarity_boost = float(similarity_boost)
        style = float(style)
    except:
        await update.effective_chat.send_message(f'Usage: /editvoicesettings <voice_id> <stability> <similarity_boost> <style> <use_speaker_boost (True/False)>')
        return
    settings = VoiceSettings(
        stability=float(stability),
        similarity_boost=float(similarity_boost),
        style=float(style),
        use_speaker_boost=use_speaker_boost == 'True'
    )
    edit_voice_settings(voice_id, settings)
    await update.effective_chat.send_message(f'Voice settings updated successfully!')

async def delete_voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        voice_id = context.args[0]
        delete_voice(voice_id)
        await update.effective_chat.send_message(f'Voice deleted successfully!')
    except:
        await update.effective_chat.send_message(f'Usage: /deletevoice <voice_id>')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer('Cancelled', show_alert=True)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
    return ConversationHandler.END

convo = ConversationHandler(
    entry_points=[CommandHandler('clone', clone)],
    states={
        'choose_telephone': [CallbackQueryHandler(choose_telephone, pattern=r'clone_choice', block=False)],
        'set_name': [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
        'set_description': [MessageHandler(filters.TEXT & ~filters.COMMAND, set_description)]
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern=r'clone_cancel', block=False)],
    allow_reentry=True
)

async def chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(update.effective_chat.id)

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global thought_messages
    query = update.callback_query
    s, chat_id, message_id = query.data.split('_')
    if s == 'complete':
        await query.answer('Completing...')
        message = await update.effective_chat.send_message('<i>Completing...</i>', parse_mode='HTML')
        async with AsyncClient(timeout=120) as client:
            response = await client.post('http://localhost:47549/complete', json={
                'chatId': chat_id,
                'messageId': message_id
            })
        response = response.json()["message"].replace('User 1: ', '').replace('User 2: ', '')
        if chat_id not in thought_messages.keys():
            thought_messages[chat_id] = {}
        response_id = str(random.randint(0, 1000000))
        thought_messages[chat_id][response_id] = response
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('Send text', callback_data=f'send_{chat_id}_{response_id}'),
            InlineKeyboardButton('Send audio', callback_data=f'audio_{chat_id}_{response_id}')
            ]
            ])
        await message.edit_text(f'<code>{response}</code>', parse_mode='HTML', reply_markup=keyboard)
        save_thought_messages()
        
    elif s == 'send':
        pickle.dump({
            'type': 'text',
            'telephone': chat_id,
            'message': thought_messages[chat_id][message_id],
            'filename': f'{chat_id}_{message_id}.pkl'
        }, open(f'sendable_messages/{chat_id}_{message_id}.pkl', 'wb'))
        await query.answer('Queued')
    elif s == 'audio':
        msg = await update.effective_message.reply_text('Generating audio...')
        audio, output_file = await text_to_speech(thought_messages[chat_id][message_id], to_ogg=True, to_base64=True, voice_id=voice_id)
        await msg.delete()
        pickle.dump({
            'type': 'audio',
            'telephone': chat_id,
            'message': audio,
            'filename': f'{chat_id}_{message_id}.pkl',
            'audio_filename': output_file
        }, open(f'sendable_messages/{chat_id}_{message_id}.pkl', 'wb'))
        await query.answer('Queued')

def main():
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    application.add_handler(convo)
    application.add_handler(CommandHandler('voices', get_voices, block=False))
    application.add_handler(CommandHandler('setvoiceid', set_voice_id, block=False))
    application.add_handler(CommandHandler('start', start, block=False))
    application.add_handler(CommandHandler('chatid', chat_id, block=False))
    application.add_handler(CommandHandler('editvoicesettings', edit_voice_settings_command, block=False))
    application.add_handler(CallbackQueryHandler(callback_query, block=False))
    application.run_polling()

if __name__ == '__main__':
    main()