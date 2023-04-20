import asyncio
import json
import random
import string
import aiohttp
import websockets
import gpu_api

def read_json(config_file):
    with open(config_file) as file:
        return json.load(file)
personal_params_file = "personal_params.json"
preprompt_file = "preprompt.json"

params = read_json("params.json")
personal_params = read_json(personal_params_file)
config = read_json("config.json")
preprompts = read_json(preprompt_file)
MM_URL = config["MM_URL"]
MM_TOKEN = config["MM_TOKEN"]
MM_WEBSOCKET_URL = f"{MM_URL}/api/v4/websocket"
GPU_SERVER = config["GPU_SERVER"]
GRADIO_FN = config["GRADIO_FN"]

async def get_user_id():
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{MM_URL}/api/v4/users/me", headers=headers) as response:
            user_data = await response.json()
            return user_data["id"]

async def post_user_typing(channel_id, user_id):
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "channel_id": f'{channel_id}',
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{MM_URL}/api/v4/users/{user_id}/typing", headers=headers, json=data) as response:
            pass

async def send_message(channel_id, message, root_id):
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "channel_id": channel_id,
        "message": message,
        "root_id": root_id
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{MM_URL}/api/v4/posts", headers=headers, json=data) as response:
            pass

async def get_message(post_id):
    headers = {
        "Authorization": f"Bearer {MM_TOKEN}"
    }
    data = {
        "direction": "down"
    }
    url = f"{MM_URL}/api/v4/posts/{post_id}/thread"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, json=data) as response:
            data = await response.read()
            data = data.decode()
            data = json.loads(data)
            sorted_posts = sorted(data["posts"].values(), key=lambda post: post["create_at"])
            return sorted_posts

async def handle_message(message_data):
    sender_id = message_data["user_id"]
    bot_user_id = await get_user_id()
    if sender_id == bot_user_id:
        return
    channel_id = message_data["channel_id"]
    message_text = message_data["message"]
    if message_data["root_id"] == "":
        root_id = message_data["id"]
    else:
        root_id = message_data["root_id"]
    if message_text[0] == "€" or message_text[0] == "\\":
        command = message_text[1:].split()
        for i in range(len(command)):
            command[i] = command[i].lower()
        if command[0] == "help":
            await send_message(channel_id, f"`€set <parameter_name> <parameter_value> #sets <parameter_name> to <parameter_value>`\n`€get <parameter_name> #gets <value> of <parameter_name>`\n`€getparams #gets all params`\n`€set_assistant_tag <tag> #default = ### Assistant:`\n`€set_user_tag <tag> #default = ### Human:`\n`€set_context <context> #sets personal context`\n`€get_context #gets personal context`\n`€get_assistant_tag #gets personal assistant tag`\n`€get_user_tag #gets personal user tag`\n`€reset_prompts`\n`€reset_params`", root_id)
        if command[0] == "set":
            if sender_id not in personal_params:
                personal_params[sender_id] = params
            if command[1] in personal_params[sender_id]:
                if isinstance(personal_params[sender_id][command[1]], int):
                    try:
                        converted_value = int(command[2])
                    except ValueError:
                        return
                elif isinstance(personal_params[sender_id][command[1]], float):
                    try:
                        converted_value = float(command[2])
                    except ValueError:
                        return
                elif isinstance(personal_params[sender_id][command[1]], bool):
                    try:
                        converted_value = bool(command[2])
                    except ValueError:
                        return
                personal_params[sender_id][command[1]] = converted_value
                with open(personal_params_file, 'w', encoding='utf8') as file:
                    json.dump(personal_params,file)
                await send_message(channel_id, f"`{command[1]} set to {personal_params[sender_id][command[1]]}`",root_id)
        elif command[0] == "reset_params":
            personal_params.pop(sender_id)
            with open(personal_params_file, 'w', encoding='utf8') as file:
                json.dump(personal_params,file)
        elif command[0] == "get":
            if command[1] in params:
                if sender_id in personal_params:
                    await send_message(channel_id, f"`{command[1]} == {personal_params[sender_id][command[1]]} {type(params[command[1]])}`",root_id)
                else:
                    await send_message(channel_id, f"`{command[1]} == {params[command[1]]} {type(params[command[1]])}`",root_id)
        elif command[0] == "getparams":
            if sender_id in personal_params:
                await send_message(channel_id, "`"+str(personal_params[sender_id])+"`", root_id)
            else:
                await send_message(channel_id, "`"+str(params)+"`", root_id)
        elif command[0] == "get_assistant_tag":
            if sender_id in preprompts:
                await send_message(channel_id, "`"+str(preprompts[sender_id]["assistant_tag"])+"`", root_id)
            else:
                await send_message(channel_id, "`"+str(preprompts["default"]["assistant_tag"])+"`", root_id)
        elif command[0] == "get_user_tag":
            if sender_id in preprompts:
                await send_message(channel_id, "`"+str(preprompts[sender_id]["user_tag"])+"`", root_id)
            else:
                await send_message(channel_id, "`"+str(preprompts["default"]["user_tag"])+"`", root_id)
        elif command[0] == "get_context":
            if sender_id in preprompts:
                await send_message(channel_id, "`"+str(preprompts[sender_id]["context"])+"`", root_id)
            else:
                await send_message(channel_id, "`"+str(preprompts["default"]["context"])+"`", root_id)
        elif command[0] == "set_assistant_tag":
            if sender_id not in preprompts:
                preprompts[sender_id] = {}
                preprompts[sender_id]["assistant_tag"] = preprompts["default"]["assistant_tag"]
                preprompts[sender_id]["user_tag"] = preprompts["default"]["user_tag"]
                preprompts[sender_id]["context"] = preprompts["default"]["context"]
            preprompts[sender_id]["assistant_tag"] = message_text[19:]
            with open(preprompt_file, 'w', encoding='utf8') as file:
                json.dump(preprompts,file)
        elif command[0] == "set_user_tag":
            if sender_id not in preprompts:
                preprompts[sender_id] = {}
                preprompts[sender_id]["assistant_tag"] = preprompts["default"]["assistant_tag"]
                preprompts[sender_id]["user_tag"] = preprompts["default"]["user_tag"]
                preprompts[sender_id]["context"] = preprompts["default"]["context"]
            preprompts[sender_id]["user_tag"] = message_text[13:]
            with open(preprompt_file, 'w', encoding='utf8') as file:
                json.dump(preprompts,file)
        elif command[0] == "set_context":
            if sender_id not in preprompts:
                preprompts[sender_id] = {}
                preprompts[sender_id]["assistant_tag"] = preprompts["default"]["assistant_tag"]
                preprompts[sender_id]["user_tag"] = preprompts["default"]["user_tag"]
                preprompts[sender_id]["context"] = preprompts["default"]["context"]
            preprompts[sender_id]["context"] = message_text[12:]
            with open(preprompt_file, 'w', encoding='utf8') as file:
                json.dump(preprompts,file)
        elif command[0] == "reset_prompts":
            preprompts.pop(sender_id)
            with open(preprompt_file, 'w', encoding='utf8') as file:
                json.dump(preprompts,file)
    else:
        if message_data["root_id"] == "":
            if config["BOT_USERNAME"] in message_text.lower():
                message_thread = await get_message(message_data["id"])
                response_text = await gpu_api.get_result(message_text, sender_id, message_thread, bot_user_id, config["BOT_USERNAME"].lower(), preprompts, GPU_SERVER, GRADIO_FN, personal_params, params, post_user_typing)
                await send_message(channel_id, response_text, root_id)
        else:
            message_thread = await get_message(message_data["root_id"])
            response_text = await gpu_api.get_result(message_text, sender_id, message_thread, bot_user_id, config["BOT_USERNAME"].lower(), preprompts, GPU_SERVER, GRADIO_FN, personal_params, params, post_user_typing)
            await send_message(channel_id, response_text, root_id)

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
