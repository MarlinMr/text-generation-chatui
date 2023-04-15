import asyncio
import json
import random
import string
import aiohttp
import websockets

def read_json(config_file):
    with open(config_file) as file:
        return json.load(file)

params = read_json("params.json")
print(params)
config = read_json("config.json")
print(config)
MM_URL = config["MM_URL"]
MM_TOKEN = config["MM_TOKEN"]
MM_WEBSOCKET_URL = f"{MM_URL}/api/v4/websocket"
GRADIO_FN = config["GRADIO_FN"]

def random_hash():
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(9))

async def get_user_id():
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{MM_URL}/api/v4/users/me", headers=headers) as response:
            user_data = await response.json()
            return user_data["id"]

async def send_message(channel_id, message):
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "channel_id": channel_id,
        "message": message,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{MM_URL}/api/v4/posts", headers=headers, json=data) as response:
            pass

async def handle_message(message_data):
    sender_id = message_data["user_id"]
    my_user_id = await get_user_id()
    if sender_id == my_user_id:
        return

    channel_id = message_data["channel_id"]
    message_text = message_data["message"]

    response_text = await get_result(message_text)
    await send_message(channel_id, response_text)

async def run(context):
    server = "localhost"
    payload = json.dumps([context, params])
    session = random_hash()
    async with websockets.connect(f"ws://{server}:7860/queue/join") as websocket:
        while content := json.loads(await websocket.recv()):
            # Python3.10 syntax, replace with if elif on older
            match content["msg"]:
                case "send_hash":
                    await websocket.send(json.dumps({
                        "session_hash": session,
                        "fn_index": GRADIO_FN
                    }))
                case "estimation":
                    pass
                case "send_data":
                    await websocket.send(json.dumps({
                        "session_hash": session,
                        "fn_index": GRADIO_FN,
                        "data": [
                            payload
                        ]
                    }))
                case "process_starts":
                    pass
                case "process_generating" | "process_completed":
                    yield content["output"]["data"][0]
                    # You can search for your desired end indicator and
                    #  stop generation by closing the websocket here
                    if (content["msg"] == "process_completed"):
                        break



#    greeting = "Hello there! How can I help you today? Do you have any questions or topics you'd like to discuss?"
#    prompt = input("Prompt: ")
#    guide = f"Common sense question and answers \n Question: {prompt} Factual answer:"
#
async def get_result(message):
    async for response in run(message):
        # Print intermediate steps
        answer = response.replace(message, "", 1)
        print(answer)
    # Print final result
    print(response)
    return response


async def main():
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}",
    }
    async with websockets.connect(MM_WEBSOCKET_URL, extra_headers=headers) as websocket:
        while True:
            message = await websocket.recv()
            message_data = json.loads(message)
            event = message_data.get("event")

            if event == "posted":
                post_data = json.loads(message_data["data"]["post"])
                await handle_message(post_data)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
