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
preprompts = read_json("preprompt.json")
#print(preprompts)
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

    if message_text[0] == "€" or message_text[0] == "\\":
        command = message_text[1:].split()
        print(command)
        if command[0] == "set":
            print(command[0])
            if command[1] in params:
                if isinstance(params[command[1]], int):
                    print("is int")
                    try:
                        converted_value = int(command[2])
                    except ValueError:
                        return
                elif isinstance(params[command[1]], float):
                    print("is float")
                    try:
                        converted_value = float(command[2])
                    except ValueError:
                        return
                elif isinstance(params[command[1]], bool):
                    print("is bool")
                    try:
                        converted_value = bool(command[2])
                    except ValueError:
                        return
                params[command[1]] = converted_value
                await send_message(channel_id, f"`{command[1]} set to {params[command[1]]}`")
        elif command[0] == "get":
            if command[1] in params:
                await send_message(channel_id, f"`{command[1]} == {params[command[1]]} {type(params[command[1]])}`")
        elif command[0] == "getparams":
            await send_message(channel_id, "`"+str(params)+"`")


    else:
        response_text = await get_result(message_text, sender_id)
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
async def get_result(message, author):
#    char_greeting = f"{preprompts['char_name']}: {preprompts['char_greeting']}"
#    example_dialogue = preprompts['example_dialogue'].replace("{{char}}", preprompts["char_name"])
#    example_dialogue = example_dialogue.replace("{{user}}", "Question")
#    context = f"{preprompts['char_persona']} \n{char_greeting} {example_dialogue} \nQuestion: {message} \n{preprompts['char_name']}:"
    context = f"Below is an instruction that describes a task. Write a response that appropriately completes the request. \n### Human: {message}\n### Assistant:"
    async for response in run(context):
        # Print intermediate steps
        answer = response.replace(context, "", 1)
        print(answer)
    # Print final result
#    print(answer)
    if "### Human" in answer:
        answer = answer.split("### Human")[0]
    if answer[0] == " ":
        answer = answer[1:]
    return answer


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
                post = json.loads(message_data["data"]["post"])
                if post["channel_id"] == config["CHANNEL_ID"]:
                    if post["type"] == "":
                        if not post.get("props", {}).get("from_bot", False):
                            post_data = json.loads(message_data["data"]["post"])
                            await handle_message(post_data)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
