# WhatsApp Assistant

A WhatsApp bot that uses AI to help manage conversations by transcribing voice messages using OpenAI's Whisper, completing conversations using OpenAI's LLM models, and generating voice responses using ElevenLabs.

## Features

- 🎙️ Voice message transcription using OpenAI's Whisper
- 💬 AI-powered conversation completion
- 🔊 Text-to-speech responses using ElevenLabs
- 🗣️ Voice cloning and management capabilities
- 🤖 Telegram bot integration for message management
- 🔄 Audio format conversion between MP3, OGG, and Opus

## Prerequisites

- Python 3.12+
- ffmpeg installed on your system
- Valid API keys for:
  - OpenAI
  - ElevenLabs
  - Telegram Bot
  - LogFire (optional, for logging)

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
- Ubuntu/Debian: `sudo apt-get install ffmpeg libmp3lame0`
- macOS: `brew install ffmpeg`
- Windows: Download from the [official ffmpeg website](https://ffmpeg.org/download.html)

5. Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

## Configuration

Edit the `.env` file with your API keys and settings:

```env
LOGIFRE_TOKEN=your_logfire_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id (create a group, add the bot and get the chat id with the /chatid command)
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id
OPENAI_MODEL=your_openai_model (message format is adapted to o1-preview, if you want to use a non-o model, the first message role should be "system")
MY_PHONE_NUMBER=your_phone_number (with the country code (but no +))
```

## Usage

The application consists of three main components that need to be running (you can use the "screen" package to run some of them in the background):

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
   - Clone voices from audio samples
   - Manage voice settings and profiles

## Voice Management Features

The assistant includes comprehensive voice management capabilities:
- Clone voices from audio samples
- Edit voice settings and profiles
- List available voices
- Delete voices
- Customize voice parameters

## Project Structure

- `api.py`: FastAPI server handling message processing, AI completions, and voice management
- `whatsapp.py`: WhatsApp client integration with message handling
- `bot.py`: Telegram bot for message management and voice control
- `utils.py`: Utility functions for audio processing, transcription, and voice synthesis

Key functions:
- Audio conversion between formats (MP3, OGG, Opus)
- Voice transcription with OpenAI Whisper
- Text-to-speech with ElevenLabs
- Voice cloning and management
- Conversation management and completion

## Telegram Bot Commands

The Telegram bot provides several commands for managing the assistant:
- `/start` - Dummy command
- `/clone` - Clone a voice from samples
- `/voices` - List available voices
- `/chatid` - Get your Telegram chat ID
- `/setvoiceid` - Set the voice id you want to use for audio responses
- `/editvoicesettings` - Edit the settings for the voice model
- `/deletevoice` - Exactly what you think it does
- Voice editing and management commands

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
- OpenAI for Whisper API and language models
- ElevenLabs for text-to-speech and voice cloning capabilities
- python-telegram-bot for Telegram integration

