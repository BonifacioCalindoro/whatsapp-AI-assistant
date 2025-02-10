from fastapi import FastAPI
import uvicorn, pickle, os, logfire
from openai import AsyncOpenAI
from utils import convert_from_b64_and_transcribe
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

bot = Bot(os.getenv('TELEGRAM_BOT_TOKEN'))

openai = AsyncOpenAI(
    api_key=os.getenv('OPENAI_API_KEY')
)

logfire.configure(
    send_to_logfire='if-token-present',
    service_name='api',
    scrubbing=False
)

app = FastAPI()

if not os.path.exists('conversations'):
    os.makedirs('conversations')

async def send_to_telegram(chat_id, message):
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Complete", callback_data=f'complete_{chat_id}_{message["id"].split("_")[2]}')]
        ]
    )
    await bot.send_message(os.getenv('TELEGRAM_CHAT_ID'), f'<b>{message["sender"]["shortName"]}</b>: <i>{message["content"]}</i>', parse_mode='HTML', reply_markup=keyboard)


def load_conversations():
    conversations = {}
    for telephone in [telephone.replace('.pkl', '') for telephone in os.listdir('conversations')]:
        conversations[telephone] = pickle.load(open(f'conversations/{telephone}.pkl', 'rb'))
    return conversations

def save_conversation(telephone, conversation):
    pickle.dump(conversation, open(f'conversations/{telephone}.pkl', 'wb'))

conversations = load_conversations()

def format_conversation(conversation, from_message):
    formatted_conversation = []
    formatted_conversation.append({"role": "user", "content": "Eres un asistente personal que puede completar conversaciones en nombre de Usuario 1. Lee la conversación y responde como si fueras Usuario 1, respetando el tono de voz y el estilo de escritura de Usuario 1."})
    for message in conversation:
        formatted_conversation.append({"role": "assistant" if message["fromMe"] else "user", "content": f'Usuario 1: {message["content"]}' if message["fromMe"] else f'Usuario 2: {message["content"]}'})
        if message["messageId"] == from_message:
            break
    return formatted_conversation


async def complete_conversation(chat_id, from_message):
    conversation = conversations[chat_id]
    formatted_conversation = format_conversation(conversation, from_message)
    response = await openai.chat.completions.create(
        model=os.getenv('OPENAI_MODEL'),
        messages=formatted_conversation
    )
    return response.choices[0].message.content

@app.post('/complete')
async def complete(data: dict):
    global conversations
    chat_id = data['chatId']
    message_id = data['messageId']
    if chat_id not in conversations.keys():
        return {"message": "Chat not found", "error": True}
    else:
        response = await complete_conversation(chat_id, from_message=message_id)
        return {"message": response, "error": False}

@app.post('/new_message')
async def new_message(message: dict):
    global conversations
    chat_id = message["chatId"]["user"]
    if len(chat_id) > 14:
        return
    if chat_id not in conversations.keys():
        conversations[chat_id] = []
    try:
        int(message["from"].split("@")[0])
    except:
        return
    if message["sender"]["shortName"] in ["None", "none", "NONE", None]:
        return
    if message.get("base_64_audio") != None:
        transcription = await convert_from_b64_and_transcribe(message["base_64_audio"])
        message["content"] = transcription
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
    return {"message": "Message received"}


if __name__ == '__main__':
    uvicorn.run(app, host='localhost', port=47549)
