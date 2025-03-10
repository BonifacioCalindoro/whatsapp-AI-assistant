from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from httpx import AsyncClient
from elevenlabs.types import VoiceSettings
from dotenv import load_dotenv
import random, os, pickle, logfire

from utils import text_to_speech, edit_voice_settings, delete_voice

logfire.configure(
    send_to_logfire='if-token-present',
    token=os.getenv('LOGFIRE_TOKEN'),
    service_name='bot',
    scrubbing=False
)

load_dotenv()

voice_id = os.getenv('ELEVENLABS_VOICE_ID')

if not os.path.exists('sendable_messages'):
    os.makedirs('sendable_messages')

def load_thought_messages():
    with logfire.span('load_thought_messages'):
        try:
            if os.path.exists('thought_messages.pkl'):
                messages = pickle.load(open('thought_messages.pkl', 'rb'))
                logfire.info("Thought messages loaded successfully", count=sum(len(msgs) for msgs in messages.values()))
                return messages
            else:
                logfire.info("No thought messages file found, creating new")
                return {}
        except Exception as e:
            logfire.error("Error loading thought messages", error=e)
            return {}

thought_messages = load_thought_messages()

def save_thought_messages():
    with logfire.span('save_thought_messages'):
        try:
            pickle.dump(thought_messages, open('thought_messages.pkl', 'wb'))
            logfire.info("Thought messages saved successfully", count=sum(len(msgs) for msgs in thought_messages.values()))
        except Exception as e:
            logfire.error("Error saving thought messages", error=e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('start', chat_id=update.effective_chat.id):
        try:
            await update.message.reply_text("Yes, I'm alive!")
            logfire.info("Start command executed successfully")
        except Exception as e:
            logfire.error("Error executing start command", error=e)

async def clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('clone', chat_id=update.effective_chat.id):
        try:
            telephones = [tel.replace('.pkl', '') for tel in os.listdir('samples') if tel.endswith('.pkl')]
            keyboard = [InlineKeyboardButton(tel, callback_data=f'clone_choice_{tel}') for tel in telephones]
            keyboard_rows = [keyboard[i:i+3] for i in range(0, len(keyboard), 3)]
            reply_markup = InlineKeyboardMarkup(keyboard_rows)
            await update.message.reply_text("Choose a telephone to clone:", reply_markup=reply_markup)
            logfire.info("Clone command executed successfully")
            return 'choose_telephone'
        except Exception as e:
            logfire.error("Error executing clone command", error=e)
            return ConversationHandler.END

async def choose_telephone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('choose_telephone', chat_id=update.effective_chat.id):
        try:
            query = update.callback_query
            data = query.data.split('_')[-1]
            await query.answer()
            context.user_data['telephone'] = data
            message = await update.effective_chat.send_message(f'Set a name for the new voice:', parse_mode='HTML')
            logfire.info("Telephone chosen successfully", telephone=data)
            return 'set_name'
        except Exception as e:
            logfire.error("Error choosing telephone", error=e)
            return ConversationHandler.END

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('set_name', chat_id=update.effective_chat.id):
        try:
            context.user_data['name'] = update.effective_message.text
            await update.effective_chat.send_message(f'Set a description for the new voice:', parse_mode='HTML')
            logfire.info("Name set successfully", name=context.user_data['name'])
            return 'set_description'
        except Exception as e:
            logfire.error("Error setting name", error=e)
            return ConversationHandler.END

async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('set_description', chat_id=update.effective_chat.id):
        try:
            context.user_data['description'] = update.effective_message.text
            await update.effective_chat.send_message(f'Cloning...')
            logfire.info("Description set successfully", description=context.user_data['description'])
            
            try:
                async with AsyncClient(timeout=120) as client:
                    response = await client.post('http://localhost:47549/clone', json={
                        'telephone': context.user_data['telephone'],
                        'name': context.user_data['name'],
                        'prompt': context.user_data['description']
                    })
                    response = response.json()
                    if response['error']:
                        await update.effective_chat.send_message(f'Error: {response["message"]}')
                        logfire.error("Error from clone API", message=response["message"])
                        return ConversationHandler.END
                    else:
                        voices, voice = response['voices'], response['voice']
                        await update.effective_chat.send_message(f'Voice <code>{voice["voice_id"]}</code> cloned successfully!', parse_mode='HTML')
                        logfire.info("Voice cloned successfully", voice_id=voice["voice_id"])
                return ConversationHandler.END
            except Exception as e:
                logfire.error("Error during API call to clone", error=e)
                await update.effective_chat.send_message(f'Error cloning voice: {str(e)}')
                return ConversationHandler.END
        except Exception as e:
            logfire.error("Error setting description", error=e)
            return ConversationHandler.END

async def get_voices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('get_voices', chat_id=update.effective_chat.id):
        try:
            async with AsyncClient(timeout=120) as client:
                response = await client.get('http://localhost:47549/voices')
                response = response.json()
            voices = response['voices']
            await update.effective_chat.send_message(f'Voices:')
            msg = ''
            for v in voices:
                msg += f'<code>{v["voice_id"]}</code>: {v["name"]}\n'
            await update.effective_chat.send_message(msg, parse_mode='HTML')
            logfire.info("Voices retrieved successfully", count=len(voices))
        except Exception as e:
            logfire.error("Error getting voices", error=e)
            await update.effective_chat.send_message(f'Error getting voices: {str(e)}')

async def set_voice_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('set_voice_id', chat_id=update.effective_chat.id):
        try:
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
                logfire.info("Voice ID set successfully", voice_id=voice_id)
            else:
                await update.effective_chat.send_message(f'Voice ID not found')
                logfire.warning("Voice ID not found", attempted_voice_id=id)
        except Exception as e:
            logfire.error("Error setting voice ID", error=e)
            await update.effective_chat.send_message(f'Error setting voice ID: {str(e)}')

async def edit_voice_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('edit_voice_settings_command', chat_id=update.effective_chat.id):
        try:
            try:
                voice_id, stability, similarity_boost, style, use_speaker_boost = context.args
                stability = float(stability)
                similarity_boost = float(similarity_boost)
                style = float(style)
            except:
                await update.effective_chat.send_message(f'Usage: /editvoicesettings <voice_id> <stability> <similarity_boost> <style> <use_speaker_boost (True/False)>')
                logfire.warning("Invalid arguments for edit voice settings")
                return
            settings = VoiceSettings(
                stability=float(stability),
                similarity_boost=float(similarity_boost),
                style=float(style),
                use_speaker_boost=use_speaker_boost == 'True'
            )
            edit_voice_settings(voice_id, settings)
            await update.effective_chat.send_message(f'Voice settings updated successfully!')
            logfire.info("Voice settings updated successfully", voice_id=voice_id, settings=settings)
        except Exception as e:
            logfire.error("Error editing voice settings", error=e)
            await update.effective_chat.send_message(f'Error editing voice settings: {str(e)}')

async def delete_voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('delete_voice_command', chat_id=update.effective_chat.id):
        try:
            try:
                voice_id = context.args[0]
                delete_voice(voice_id)
                await update.effective_chat.send_message(f'Voice deleted successfully!')
                logfire.info("Voice deleted successfully", voice_id=voice_id)
            except:
                await update.effective_chat.send_message(f'Usage: /deletevoice <voice_id>')
                logfire.warning("Invalid arguments for delete voice")
        except Exception as e:
            logfire.error("Error deleting voice", error=e)
            await update.effective_chat.send_message(f'Error deleting voice: {str(e)}')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('cancel', chat_id=update.effective_chat.id):
        try:
            query = update.callback_query
            message_id = query.message.message_id
            await query.answer('Cancelled', show_alert=True)
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            logfire.info("Operation cancelled")
            return ConversationHandler.END
        except Exception as e:
            logfire.error("Error cancelling operation", error=e)
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
    with logfire.span('chat_id', chat_id=update.effective_chat.id):
        try:
            await update.effective_chat.send_message(update.effective_chat.id)
            logfire.info("Chat ID sent", chat_id=update.effective_chat.id)
        except Exception as e:
            logfire.error("Error sending chat ID", error=e)

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with logfire.span('callback_query', chat_id=update.effective_chat.id):
        try:
            global thought_messages
            query = update.callback_query
            s, chat_id, message_id = query.data.split('_')
            
            if s == 'complete':
                with logfire.span('complete_callback', chat_id=chat_id, message_id=message_id):
                    try:
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
                        logfire.info("Message completed successfully", chat_id=chat_id, message_id=message_id)
                    except Exception as e:
                        logfire.error("Error completing message", chat_id=chat_id, message_id=message_id, error=e)
                        await update.effective_chat.send_message(f'Error completing message: {str(e)}')
                
            elif s == 'send':
                with logfire.span('send_callback', chat_id=chat_id, message_id=message_id):
                    try:
                        pickle.dump({
                            'type': 'text',
                            'telephone': chat_id,
                            'message': thought_messages[chat_id][message_id],
                            'filename': f'{chat_id}_{message_id}.pkl'
                        }, open(f'sendable_messages/{chat_id}_{message_id}.pkl', 'wb'))
                        await query.answer('Queued')
                        logfire.info("Text message queued for sending", chat_id=chat_id, message_id=message_id)
                    except Exception as e:
                        logfire.error("Error queuing text message", chat_id=chat_id, message_id=message_id, error=e)
                        await query.answer('Error queuing message')
                        
            elif s == 'audio':
                with logfire.span('audio_callback', chat_id=chat_id, message_id=message_id):
                    try:
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
                        logfire.info("Audio message queued for sending", chat_id=chat_id, message_id=message_id)
                    except Exception as e:
                        logfire.error("Error generating audio", chat_id=chat_id, message_id=message_id, error=e)
                        await update.effective_chat.send_message(f'Error generating audio: {str(e)}')
        except Exception as e:
            logfire.error("Error processing callback query", error=e)

def main():
    try:
        application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
        application.add_handler(convo)
        application.add_handler(CommandHandler('voices', get_voices, block=False))
        application.add_handler(CommandHandler('setvoiceid', set_voice_id, block=False))
        application.add_handler(CommandHandler('start', start, block=False))
        application.add_handler(CommandHandler('chatid', chat_id, block=False))
        application.add_handler(CommandHandler('editvoicesettings', edit_voice_settings_command, block=False))
        application.add_handler(CommandHandler('deletevoice', delete_voice_command, block=False))
        application.add_handler(CallbackQueryHandler(callback_query, block=False))
        logfire.info("Application initialized successfully")
        application.run_polling()
    except Exception as e:
        logfire.error("Error in main function", error=e)

if __name__ == '__main__':
    main()