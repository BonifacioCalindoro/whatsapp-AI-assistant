from fastapi import FastAPI
import uvicorn, pickle, os, logfire
from openai import AsyncOpenAI, RateLimitError
from utils import convert_from_b64_and_transcribe, convert_opus_base64_to_mp3, clone_voice_from_samples, get_voices
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

logfire.configure(
    send_to_logfire='if-token-present',
    service_name='api',
    scrubbing=False
)

load_dotenv()

bot = Bot(os.getenv('TELEGRAM_BOT_TOKEN'))

openai = AsyncOpenAI(
    api_key=os.getenv('OPENAI_API_KEY')
)

app = FastAPI()

if not os.path.exists('conversations'):
    os.makedirs('conversations')

if not os.path.exists('samples'):
    os.makedirs('samples')

if not os.path.exists('audios'):
    os.makedirs('audios')

async def send_to_telegram(chat_id, message):
    with logfire.span('send_to_telegram', chat_id=chat_id, message=message):
        try:
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Complete", callback_data=f'complete_{chat_id}_{message["id"].split("_")[2]}')]
                ]
            )
            result = await bot.send_message(os.getenv('TELEGRAM_CHAT_ID'), f'<b>{message["sender"]["shortName"]}</b>: <i>{message["content"]}</i>', parse_mode='HTML', reply_markup=keyboard)
            logfire.info("Message sent to telegram")
        except Exception as e:
            logfire.error("Error sending message to telegram", error=e)
            return
        return result

def load_samples():
    with logfire.span('load_samples'):
        try:
            samples = {}
            for telephone in [telephone.replace('.pkl', '') for telephone in os.listdir('samples')]:
                samples[telephone] = pickle.load(open(f'samples/{telephone}.pkl', 'rb'))
            logfire.info("Samples loaded successfully")
            return samples
        except Exception as e:
            logfire.error("Error loading samples", error=e)
            return {}

def load_conversations():
    with logfire.span('load_conversations'):
        try:
            conversations = {}
            for telephone in [telephone.replace('.pkl', '') for telephone in os.listdir('conversations')]:
                conversations[telephone] = pickle.load(open(f'conversations/{telephone}.pkl', 'rb'))
            logfire.info("Conversations loaded successfully")
            return conversations
        except Exception as e:
            logfire.error("Error loading conversations", error=e)
            return {}

def save_conversation(telephone, conversation):
    with logfire.span('save_conversation', telephone=telephone):
        try:
            pickle.dump(conversation, open(f'conversations/{telephone}.pkl', 'wb'))
            logfire.info("Conversation saved successfully", telephone=telephone)
        except Exception as e:
            logfire.error("Error saving conversation", telephone=telephone, error=e)

conversations = load_conversations()
samples = load_samples()

def save_sample(telephone, sample):
    with logfire.span('save_sample', telephone=telephone):
        try:
            pickle.dump(sample, open(f'samples/{telephone}.pkl', 'wb'))
            logfire.info("Sample saved successfully", telephone=telephone)
        except Exception as e:
            logfire.error("Error saving sample", telephone=telephone, error=e)

def format_conversation(conversation, from_message):
    with logfire.span('format_conversation', from_message=from_message):
        try:
            formatted_conversation = []
            formatted_conversation.append({"role": "user" if os.getenv('OPENAI_MODEL').startswith('o') else "system", "content": "You are a personal assistant that can complete conversations on behalf of User 1. Read the conversation and respond as if you were User 1, respecting the tone of voice and writing style of User 1."})
            for message in conversation:
                formatted_conversation.append({"role": "assistant" if message["fromMe"] else "user", "content": f'User 1: {message["content"]}' if message["fromMe"] else f'User 2: {message["content"]}'})
                if message["messageId"] == from_message:
                    break
            logfire.info("Conversation formatted successfully")
            return formatted_conversation
        except Exception as e:
            logfire.error("Error formatting conversation", error=e)
            return []


async def complete_conversation(chat_id, from_message):
    with logfire.span('complete_conversation', chat_id=chat_id, from_message=from_message):
        try:
            conversation = conversations[chat_id]
            formatted_conversation = format_conversation(conversation, from_message)
            try:
                response = await openai.chat.completions.create(
                    model=os.getenv('OPENAI_MODEL'),
                    messages=formatted_conversation
                )
            except RateLimitError as e:
                logfire.warning("Rate limit error, trying with truncated conversation", error=e)
                # Try again with only last 50 messages
                truncated_conversation = formatted_conversation[:1] + formatted_conversation[-min(50, len(formatted_conversation)-1):]
                try:
                    response = await openai.chat.completions.create(
                        model=os.getenv('OPENAI_MODEL'),
                        messages=truncated_conversation
                    )
                except Exception as e2:
                    logfire.error("Error completing conversation with truncated messages", error=e2)
                    return {"message": str(e2), "error": True}
            logfire.info("Conversation completed successfully")
            return response.choices[0].message.content
        except Exception as e:
            logfire.error("Error completing conversation", error=e)
            return {"message": str(e), "error": True}

@app.post('/delete_sample')
async def delete_sample(data: dict):
    with logfire.span('delete_sample', telephone=data.get('telephone'), sample=data.get('sample')):
        try:
            global samples
            telephone = data['telephone']
            sample = data['sample']
            samples[telephone] = [s for s in samples.get(telephone, []) if s != f'audios/{sample}']
            save_sample(telephone, samples[telephone])
            os.remove(f'audios/{sample}')
            logfire.info("Sample deleted successfully", telephone=telephone, sample=sample)
            return {"message": "Sample deleted", "error": False}
        except Exception as e:
            logfire.error("Error deleting sample", error=e)
            return {"message": str(e), "error": True}

@app.post('/complete')
async def complete(data: dict):
    with logfire.span('complete', chat_id=data.get('chatId'), message_id=data.get('messageId')):
        try:
            global conversations
            chat_id = data['chatId']
            message_id = data['messageId']
            if chat_id not in conversations.keys():
                logfire.warning("Chat not found", chat_id=chat_id)
                return {"message": "Chat not found", "error": True}
            else:
                response = await complete_conversation(chat_id, from_message=message_id)
                logfire.info("Completion successful", chat_id=chat_id)
                return {"message": response, "error": False}
        except Exception as e:
            logfire.error("Error in complete endpoint", error=e)
            return {"message": str(e), "error": True}
    
@app.post('/clone')
async def clone(data: dict):
    with logfire.span('clone', telephone=data.get('telephone'), name=data.get('name')):
        try:
            global samples
            telephone = data['telephone']
            if telephone not in samples.keys():
                logfire.warning("Telephone not found", telephone=telephone)
                return {"message": "Telephone not found", "error": True}
            else:
                try:
                    voice = clone_voice_from_samples(samples[telephone], data['prompt'], data['name'])
                    voices = get_voices()
                    logfire.info("Voice cloned successfully", telephone=telephone, voice=voice)
                    return {"message": voice, "error": False, "voices": voices, "voice": voice}
                except Exception as e:
                    logfire.error("Error cloning voice", telephone=telephone, error=e)
                    return {"message": str(e), "error": True}
        except Exception as e:
            logfire.error("Error in clone endpoint", error=e)
            return {"message": str(e), "error": True}

@app.get('/voices')
async def voices():
    with logfire.span('voices'):
        try:
            voices_data = get_voices().model_dump()['voices']
            logfire.info("Voices retrieved successfully", count=len(voices_data))
            return {"voices": voices_data, "error": False}
        except Exception as e:
            logfire.error("Error getting voices", error=e)
            return {"message": str(e), "error": True}

@app.post('/new_message')
async def new_message(message: dict):
    with logfire.span('new_message', chat_id=message.get("chatId", {}).get("user")):
        try:
            global conversations
            global samples
            chat_id = message["chatId"]["user"]
            if len(chat_id) > 14:
                logfire.warning("Invalid chat_id length", chat_id=chat_id)
                return
            if chat_id not in conversations.keys():
                conversations[chat_id] = []
            try:
                int(message["from"].split("@")[0])
            except:
                logfire.warning("Invalid from field", from_field=message.get("from"))
                return
            if message["sender"]["shortName"] in ["None", "none", "NONE", None]:
                logfire.warning("Invalid sender name", sender=message.get("sender"))
                return
            if message.get("base_64_audio") != None:
                from_telephone = message["from"].split("@")[0]
                if from_telephone not in samples.keys():
                    samples[from_telephone] = []
                output_file = convert_opus_base64_to_mp3(message["base_64_audio"], f"audios/{message['id'].split('_')[2]}.mp3")
                samples[from_telephone].append(output_file)
                save_sample(from_telephone, samples[from_telephone])
                retries = 3
                while retries > 0:
                    try:
                        transcription = await convert_from_b64_and_transcribe(message["base_64_audio"])
                        break
                    except Exception as e:
                        logfire.warning(f"Transcription retry {3-retries+1}/3 failed", error=e)
                        retries -= 1
                else:
                    logfire.error("All transcription retries failed")
                    return {"message": "Error transcribing audio", "error": True}
                message["content"] = transcription
                logfire.info("Audio transcribed successfully")

            if message['fromMe']:
                conversations[chat_id].append({
                    "from": message["from"].split("@")[0],
                    "fromMe": True,
                    "name": message["sender"]["shortName"],
                    "content": message["content"],
                    "messageId": message["id"].split("_")[2],
                    "timestamp": message["t"]
                    }
                )
            else:
                conversations[chat_id].append({
                    "from": message["from"].split("@")[0],
                    "fromMe": False,
                    "name": message["sender"]["shortName"],
                    "content": message["content"],
                    "messageId": message["id"].split("_")[2],
                    "timestamp": message["t"]
                })
                await send_to_telegram(chat_id, message)

            save_conversation(chat_id, conversations[chat_id])
            logfire.info("New message processed successfully", chat_id=chat_id)
            return {"message": "Message received"}
        except Exception as e:
            logfire.error("Error processing new message", error=e)
            return {"message": str(e), "error": True}


if __name__ == '__main__':
    uvicorn.run(app, host='localhost', port=47549)
