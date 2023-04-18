import asyncio
import json
import random
import aiohttp
import string
import websockets

def random_hash():
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(9))

async def run(context, author_id, GPU_SERVER, GRADIO_FN, personal_params, params):
    if author_id in personal_params:
        payload = json.dumps([context, personal_params[author_id]])
    else:
        payload = json.dumps([context, params])
    session = random_hash()
    async with websockets.connect(f"ws://{GPU_SERVER}:7860/queue/join") as websocket:
        while content := json.loads(await websocket.recv()):
            msg = content["msg"]
            if msg == "send_hash":
                await websocket.send(json.dumps({
                    "session_hash": session,
                    "fn_index": GRADIO_FN
                }))
            if msg == "estimation":
                pass
            if msg == "send_data":
                await websocket.send(json.dumps({
                    "session_hash": session,
                    "fn_index": GRADIO_FN,
                    "data": [payload]
                }))
            if msg == "process_starts":
               pass
            if msg == "process_generating" or msg == "process_completed":
                yield content["output"]["data"][0]
                # You can search for your desired end indicator and
                #  stop generation by closing the websocket here
                if (content["msg"] == "process_completed"):
                    break

async def get_result(message, author_id, thread, bot_id, bot_mention_id, preprompts, GPU_SERVER, GRADIO_FN, personal_params, params, post_user_typing):
    # message = <the current message as str>
    # author_id = <author_id_id>
    # thread = <list of dicts each object has a message, channel_id and user_id>
    # bot_mention_id = <id of bot as used in a message, .lower()>
    formated_thread = ""
    if author_id in preprompts:
        assistant_tag = preprompts[author_id]["assistant_tag"]
        user_tag = preprompts[author_id]["user_tag"]
        context = preprompts[author_id]["context"]
    else:
        assistant_tag = preprompts["default"]["assistant_tag"]
        user_tag = preprompts["default"]["user_tag"]
        context = preprompts["default"]["context"]
    if bot_mention_id in thread[0]["message"].lower():
        if thread[0]["message"][:len(bot_mention_id)].lower() == bot_mention_id:
            thread[0]["message"] = thread[0]["message"].lower().replace(bot_mention_id, "", 1)
    for message in thread:
        if message["user_id"] == bot_id:
            formated_thread = formated_thread + "\n" + assistant_tag + message["message"]
        else:
            formated_thread = formated_thread + "\n" + user_tag + message["message"]
    full_context = f"{context} {formated_thread}\n{assistant_tag}"
    async for response in run(full_context, author_id, GPU_SERVER, GRADIO_FN, personal_params, params):
        answer = response.replace(full_context, "", 1)
        print(answer)
        await post_user_typing(message["channel_id"], bot_id)
    if str(user_tag) in answer:
        answer = answer.split(user_tag)[0]
    elif str(user_tag[:-1]) in answer:
        answer = answer.split(user_tag[:-1])[0]
    elif str(user_tag[:-2]) in answer:
        answer = answer.split(user_tag[:-2])[0]
    if answer[0] == " ":
        answer = answer[1:]
    if answer[:-3] == "###":
        answer = answer.replace("###", "")
    if "###" in answer:
        answer = answer.replace("#", "\#")
    if len(answer) > 4000:
        answer = answer[:4000]
    return answer

