# WhatsApp Assistant

A WhatsApp bot that uses AI to help manage conversations by transcribing voice messages, completing conversations, and generating voice responses using OpenAI's Whisper and ElevenLabs.

## Features

- 🎙️ Voice message transcription using OpenAI's Whisper
- 💬 AI-powered conversation completion
- 🔊 Text-to-speech responses using ElevenLabs
- 🤖 Telegram bot integration for message management

## Prerequisites

- Python 3.12+
- ffmpeg installed on your system
- Valid API keys for:
  - OpenAI
  - ElevenLabs
  - Telegram Bot
- WhatsApp account

## Installation

1. Clone the repository:

```bash
git clone https://github.com/BonifacioCalindoro/whatsapp-AI-assistant.git
cd whatsapp-AI-assistant
```


2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install the required packages:

```bash
pip install -r requirements.txt
```

4. Install ffmpeg:
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: Download from the [official ffmpeg website](https://ffmpeg.org/download.html)

5. Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

```bash
env
LOGIFRE_TOKEN=your_logfire_token (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id (create a group, add the bot and get the chat id with the /chatid command)
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id
OPENAI_MODEL=your_openai_model (message format is adapted to o1-preview, if you want to use a non-o model, the first message role should be "system")
```

## Usage

The application consists of three main components that need to be running (you can use the "screen" package to run them in the background):

1. Start the API server:

```bash
python api.py
```

2. Start the WhatsApp client (needs a screen session to run(not the screen package)!!):

```bash
python whatsapp.py
```
and scan the QR code

3. Start the Telegram bot:

```bash
python bot.py
```


## How it Works

1. When a WhatsApp message is received, it's processed by the WhatsApp client
2. Voice messages are automatically transcribed using OpenAI's Whisper API
3. Messages are forwarded to a Telegram bot for management
4. Users can choose to:
   - Complete the conversation using AI
   - Send text responses
   - Generate and send voice responses using ElevenLabs

## Project Structure

- `api.py`: FastAPI server handling message processing and AI completions
- `whatsapp.py`: WhatsApp client integration
- `bot.py`: Telegram bot for message management
- `utils.py`: Utility functions for audio processing and API interactions

## Limitations

- The whatsapp implementation depends on future versions of the WhatsApp Web client, so it might stop working if WhatsApp changes their web client.
- The Elevenlabs API and the OpenAI API are not free, so take that into account.
- I haven't tested with long conversations, so i still don't know how well it will work with long conversations.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [WPP_Whatsapp](https://github.com/3mora2/WPP_Whatsapp) for WhatsApp Web integration
- OpenAI for Whisper API
- ElevenLabs for text-to-speech capabilities
- python-telegram-bot for Telegram integration

