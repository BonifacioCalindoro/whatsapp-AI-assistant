import os, httpx, tempfile, base64, mimetypes
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import ffmpeg
import datetime

load_dotenv()

elevenlabs_client = ElevenLabs(
  api_key=os.getenv('ELEVENLABS_API_KEY'),
)

def convert_mp3_to_opus_ffmpeg(input_mp3, output_folder="converted/"):
    # Ensure output folder exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Generate a WhatsApp-like filename
    timestamp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).strftime("%Y%m%d")
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_folder, f"PTT-{timestamp}-WA0001.opus")
    print(f"Full output path: {output_file}")

    # Convert MP3 to WhatsApp-compatible Opus format using ffmpeg
    (
        ffmpeg
        .input(input_mp3)
        .output(output_file, audio_bitrate="32k", format="opus", acodec="libopus")
        .run(overwrite_output=True)
    )

    print(f"Converted file saved as: {output_file}")
    return open(output_file, "rb").read(), r"" + output_file

async def convert_from_b64_and_transcribe(base_64_audio: str) -> str:
    audio_data = base64.b64decode(base_64_audio.split(',')[1])
    mime_type = base_64_audio.split(',')[0].split(";")[0].split(":")[1]
    file_extension = mimetypes.guess_extension(mime_type)
    if not file_extension:
        file_extension = f'.{mime_type.split("/")[1]}'
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
        temp_file.write(audio_data)
        file_path = temp_file.name

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
                },
                files={
                    "file": open(file_path, 'rb'),
                },
                data={
                    "model": "whisper-1",
                },
                timeout=120
            )
            print(response.json())
        # Clean up temporary files
        #if os.path.exists(file_path):
        #    os.remove(file_path)
        
        return response.json()["text"]

async def text_to_speech(text: str, save: bool = False, save_path: str = None, to_base64: bool = False, to_ogg: bool = False):
    audio = elevenlabs_client.text_to_speech.convert(
        text=text,
        voice_id="W5JElH3dK1UYYAiHH7uh",
        model_id="eleven_multilingual_v2"
    )
    audio = b''.join([chunk for chunk in audio])
    with open("audio.mp3", "wb") as f:
        f.write(audio)
    if to_ogg:
        audio, output_file = convert_mp3_to_opus_ffmpeg("audio.mp3")
    if save:
        with open(save_path, "wb") as f:
            f.write(audio)
    if to_base64:
        return f'data:audio/ogg; codecs=opus;base64,{base64.b64encode(audio).decode('utf-8')}', output_file
    return audio, output_file