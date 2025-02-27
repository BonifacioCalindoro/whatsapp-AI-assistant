from WPP_Whatsapp import Create
import os, asyncio, random, pickle, logfire, requests
from dotenv import load_dotenv
import logfire
from httpx import AsyncClient
load_dotenv()

logfire.configure(
    send_to_logfire='if-token-present',
    token=os.getenv('LOGFIRE_TOKEN'),
    service_name='whatsapp',
    scrubbing=False
)

my_phone_number = os.getenv('MY_PHONE_NUMBER')

async def check_sendable_messages():
    try:
        messages = [
            {
                "type": message_data['type'],
                "telephone": message_data['telephone'],
                "message": message_data['message'],
                "filename": message_data['filename'],
                "audio_filename": message_data.get('audio_filename', None)
            }
            for message_data in [
                pickle.load(open(f'sendable_messages/{filename}', 'rb'))
                for filename in os.listdir('sendable_messages')
            ]
        ]
        if len(messages) > 0:
            logfire.info(f'Found {len(messages)} sendable messages')
        return messages
    except Exception as e:
        logfire.error('Error checking sendable messages', error=e)
        return []

creator = Create(session="whatsapp")
client = creator.start()
if creator.state != 'CONNECTED':
    raise Exception(creator.state)

async def sendable_message_checker():
        try:
            global client
            while True:
                sendable = await check_sendable_messages()
                if sendable:
                    with logfire.span(f'sending {len(sendable)} messages', messages=sendable, amount=len(sendable)):
                        try:
                            for message in sendable:
                                if message['type'] == 'text':
                                    try:
                                        result = client.sendText(
                                            to=message['telephone'],
                                            content=message['message']
                                        )
                                        logfire.info(f'Sent message to {message["telephone"]}', result=result, _tags=['sent_message'])
                                    except Exception as e:
                                        logfire.error(f'Error sending message to {message["telephone"]}', error=e, _tags=['error_sending_message'])
                                        print(e)
                                        break
                                elif message['type'] == 'audio':
                                    try:
                                        result = client.sendFile(
                                            to=message['telephone'],
                                            pathOrBase64=message['audio_filename'],
                                            nameOrOptions=message['audio_filename'].split('/')[-1],
                                            caption='audio'
                                        )
                                        
                                        logfire.info(f'Sent audio to {message["telephone"]}', result=result, _tags=['sent_audio'])
                                        os.remove(f'sendable_messages/{message["filename"]}')
                                        os.remove(message["audio_filename"])
                                    except Exception as e:
                                        logfire.error(f'Error sending audio to {message["telephone"]}', error=e, _tags=['error_sending_audio'])
                                        print(e)
                                        break
                                await asyncio.sleep(10+random.randint(1, 15))
                                if message['type'] == 'audio':
                                    try:
                                        async with AsyncClient(timeout=120) as async_client:
                                            await async_client.post('http://localhost:47549/delete_sample', json={'telephone': my_phone_number, 'sample': result['id'].split('_')[-1]+'.mp3'})
                                            logfire.info('Deleted sample after sending audio')
                                    except Exception as e:
                                        logfire.error('Error deleting sample after sending audio', error=e)
                                try:
                                    os.remove(f'sendable_messages/{message["filename"]}')
                                    logfire.info(f'Removed sendable message file {message["filename"]}')
                                except Exception as e:
                                    logfire.error(f'Error removing sendable message file {message["filename"]}', error=e)
                                    print(e)
                        except Exception as e:
                            logfire.error('Error in message sending loop', error=e)
                await asyncio.sleep(2)
        except Exception as e:
            logfire.error('Error in sendable_message_checker', error=e)

def new_message_received(message):
    with logfire.span('new_message_received', message_id=message.get('id')):
        try:
            if message.get('mimetype') != None and message.get('mimetype').startswith('audio'):
                try:
                    base_64_audio = client.downloadMedia(message['id'])
                    message["base_64_audio"] = base_64_audio
                    logfire.info('Downloaded audio media', message_id=message.get('id'))
                except Exception as e:
                    logfire.error('Error downloading audio media', message_id=message.get('id'), error=e)
            
            try:
                requests.post('http://localhost:47549/new_message', json=message)
                logfire.info('Forwarded message to API', message_id=message.get('id'))
            except Exception as e:
                logfire.error('Error forwarding message to API', message_id=message.get('id'), error=e)
        except Exception as e:
            logfire.error('Error processing received message', error=e)

def main():
    try:
        global creator
        try:
            creator.loop.create_task(sendable_message_checker())
            creator.client.onAnyMessage(new_message_received)
            logfire.info('Added sendable_message_checker task')
            creator.loop.run_forever()
        except KeyboardInterrupt:
            client.close()
            logfire.info('KeyboardInterrupt')
            return
    except Exception as e:
        logfire.error('Error in main function', error=e)
        return
    
if __name__ == "__main__":
    try:
        logfire.info('Starting whatsapp')
        main()
    except Exception as e:
        logfire.error('Error during startup', error=e)
