from fastapi import FastAPI
import uvicorn, pickle, os, logfire, json
from openai import AsyncOpenAI
from utils import convert_from_b64_and_transcribe, convert_opus_base64_to_mp3, clone_voice_from_samples, get_voices
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

if not os.path.exists('samples'):
    os.makedirs('samples')

if not os.path.exists('audios'):
    os.makedirs('audios')

async def send_to_telegram(chat_id, message):
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Complete", callback_data=f'complete_{chat_id}_{message["id"].split("_")[2]}')]
        ]
    )
    await bot.send_message(os.getenv('TELEGRAM_CHAT_ID'), f'<b>{message["sender"]["shortName"]}</b>: <i>{message["content"]}</i>', parse_mode='HTML', reply_markup=keyboard)

def load_samples():
    samples = {}
    for telephone in [telephone.replace('.pkl', '') for telephone in os.listdir('samples')]:
        samples[telephone] = pickle.load(open(f'samples/{telephone}.pkl', 'rb'))
    return samples

def load_conversations():
    conversations = {}
    for telephone in [telephone.replace('.pkl', '') for telephone in os.listdir('conversations')]:
        conversations[telephone] = pickle.load(open(f'conversations/{telephone}.pkl', 'rb'))
    return conversations

def save_conversation(telephone, conversation):
    pickle.dump(conversation, open(f'conversations/{telephone}.pkl', 'wb'))

conversations = load_conversations()
samples = load_samples()

def save_sample(telephone, sample):
    pickle.dump(sample, open(f'samples/{telephone}.pkl', 'wb'))

def format_conversation(conversation, from_message):
    formatted_conversation = []
    formatted_conversation.append({"role": "user" if os.getenv('OPENAI_MODEL').startswith('o') else "system", "content": "You are a personal assistant that can complete conversations on behalf of User 1. Read the conversation and respond as if you were User 1, respecting the tone of voice and writing style of User 1."})
    for message in conversation:
        formatted_conversation.append({"role": "assistant" if message["fromMe"] else "user", "content": f'User 1: {message["content"]}' if message["fromMe"] else f'User 2: {message["content"]}'})
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

@app.post('/delete_sample')
async def delete_sample(data: dict):
    global samples
    telephone = data['telephone']
    sample = data['sample']
    samples[telephone] = [s for s in samples.get(telephone, []) if s != sample]
    save_sample(telephone, samples[telephone])
    os.remove(f'audios/{sample}')
    return {"message": "Sample deleted", "error": False}

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
    
@app.post('/clone')
async def clone(data: dict):
    global samples
    telephone = data['telephone']
    if telephone not in samples.keys():
        return {"message": "Telephone not found", "error": True}
    else:
        try:
            voice = clone_voice_from_samples(samples[telephone], data['prompt'], data['name'])
            voices = get_voices()
            return {"message": voice, "error": False, "voices": voices, "voice": voice}
        except Exception as e:
            return {"message": str(e), "error": True}

@app.get('/voices')
async def voices():
    return {"voices": get_voices().model_dump()['voices'], "error": False}

@app.post('/new_message')
async def new_message(message: dict):
    global conversations
    global samples
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
            except:
                retries -= 1
        else:
            return {"message": "Error transcribing audio", "error": True}
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
