from WPP_Whatsapp import Create
import os
import asyncio
import random
import pickle
from dotenv import load_dotenv
import logfire
import requests
import json
import os

load_dotenv()

logfire.configure(
    send_to_logfire='if-token-present',
    service_name='whatsapp',
    scrubbing=False
)

async def check_sendable_messages():
    return [
        {
            "telephone": message_data['telephone'] if message_data['telephone'].startswith('34') else f'34{message_data["telephone"]}',
            "message": message_data['message'],
            "filename": message_data['filename']
        }
        for message_data in [
            pickle.load(open(f'sendable_messages/{filename}', 'rb'))
            for filename in os.listdir('sendable_messages')
        ]
    ]

creator = Create(session="whatsapp")
client = creator.start()
if creator.state != 'CONNECTED':
    raise Exception(creator.state)

async def sendable_message_checker():
    global client
    while True:
        sendable = await check_sendable_messages()
        if sendable:
            with logfire.span(f'sending {len(sendable)} messages', messages=sendable, amount=len(sendable)):
                for message in sendable:
                    try:
                        result = client.sendText(
                            to=message['telephone'],
                            content=message['message']
                        )
                        logfire.info(f'Sent message to {message["telephone"]}', result=result, _tags=['sent_message'])
                    except Exception as e:
                        logfire.error(f'Error sending message to {message["telephone"]}', _tags=['error_sending_message'])
                        print(e)
                        break
                    await asyncio.sleep(10+random.randint(1, 15))
                    os.remove(f'sendable_messages/{message["filename"]}')
        await asyncio.sleep(2)

def new_message_received(message):
    requests.post('http://localhost:47549/new_message', json=message)

def main():
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
    
if __name__ == "__main__":
    logfire.info('Starting whatsapp')
    main()
