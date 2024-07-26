import os
import urllib.parse
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import FastAPI, BackgroundTasks, Request, Form
from fastapi.responses import JSONResponse

from dotenv import load_dotenv

from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langfuse import Langfuse
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from slack_sdk.errors import SlackApiError

from langfuse.callback import CallbackHandler

from llm.agents import new_conversional_agent
from data_models.models import *
from llm.memory.slack_memory import slack_to_llm_memory
from data_models.constants import LOADING_INDICATOR, LOADING_BLOCK, EXAMPLE_PROMPTS


logging.config.fileConfig("logging.conf", disable_existing_loggers=False)

# get root logger
logger = logging.getLogger(__name__)


load_dotenv()


SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_CLIENT = WebClient(token=SLACK_BOT_OAUTH_TOKEN)
SLACK_BOT_DISPLAY_NAME = os.getenv("SLACK_BOT_DISPLAY_NAME")
ENVIRONMENT = os.getenv("ENVIRONMENT")

langfuse_handler = CallbackHandler()


app = FastAPI()
is_dev_env = ENVIRONMENT == "Development"
slack_history_limit = 5


@app.post("/healthcheck")
def healthcheck():
    return JSONResponse(
        content={"response_type": "in_channel", "text": "Backend is up and running!"}
    )


@app.post("/example-prompts/")
async def get_example_prompts():
    # Sample array of strings
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": "Here a couple of example prompts. For some extra data is need like a url or file etc.",
                "emoji": True,
            },
        }
    ]

    # Use a for loop to fill in the text
    for text in EXAMPLE_PROMPTS:
        block = {
            "type": "section",
            "text": {"type": "plain_text", "text": text, "emoji": True},
        }
        blocks.append(block)

    return {"blocks": blocks}


@app.post("/slack/rating/")
async def slack_rating(payload: str = Form(...)):
    # Decode the URL-encoded payload to JSON
    decoded_payload = urllib.parse.unquote(payload)
    json_payload = json.loads(decoded_payload)

    # Extract relevant data
    user_id = json_payload["user"]["id"]
    message_text = json_payload["message"]["text"]
    time_stamp = json_payload["container"]["message_ts"]
    json_payload["message"].pop("blocks", None)
    metadata = json_payload["message"].copy()
    rating = None
    
    # Iterate over the state values to find the selected radio button option
    for block_id, block_data in json_payload["state"]["values"].items():
        for action_id, action_data in block_data.items():
            if action_data["type"] == "radio_buttons":
                rating = action_data["selected_option"]["text"]["text"]
                break
        if rating:
            break

    if rating:
        langfuse_client = Langfuse()
        # Convert rating text to a numerical value (customize as needed)
        rating_value = {"Good": 3, "Ok": 2, "Bad": 1}.get(rating, 0)
        
        # Create a trace in Langfuse
        # On dev, all rating is logged
        # On prod, only the bad feedback + last 5 slack messages
        if is_dev_env or rating_value == 1: 
            if not is_dev_env:
                channel_id = json_payload["container"]["channel_id"]
                latest_slack_messages = retrive_slack_messages(channel_id)
                metadata['chat_history']=latest_slack_messages
            trace = langfuse_client.trace(
                name=f"slack-rating-{time_stamp}",
                input={"message_text": message_text},
                metadata=metadata,
            )
            # Send the score to Langfuse with the message text as a comment
            trace.score(
                name="quality",
                value=rating_value,
                comment=f"User {user_id} rated: {rating}. Message: {message_text}",
                id=f"rating_{user_id}_{time_stamp}",  # Unique idempotency key
            )
            
            # Optionally, get the trace URL for logging or debugging
            # trace_url = trace.get_trace_url()
            # print(f"Trace URL: {trace_url}")
    else:
        print("No rating found")

    return payload


# must return given payload for slack challenge:
# slack retry behaviour
# https://api.slack.com/apis/connections/events-api#retries
@app.post("/slack/event/")
async def new_slack_event(
    request: Request, payload: dict, background_tasks: BackgroundTasks
):
    signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)
    request_body = await request.body()
    timestamp = request.headers.get("x-slack-request-timestamp")
    signature = request.headers.get("x-slack-signature")

    if not signature_verifier.is_valid(
        body=request_body, timestamp=timestamp, signature=signature
    ):
        return JSONResponse(
            content={"error": "Invalid signature"}, status_code=401
        )  # Unauthorized

    try:
        if "has joined the channel" in payload["event"]["text"]:
            await new_user_handler(payload)

        # check if message is from user
        if payload["event"]["client_msg_id"]:
            # Extract all user IDs from the message using the regex
            user_id_matches = re.findall(r"<@(\w+)>", payload["event"]["text"])

            bot_name_mentioned = False

            # call slack in parallel for each match and check if bot was mentioned
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(check_user, user_id): user_id
                    for user_id in user_id_matches
                }
                for future in as_completed(futures):
                    if future.result():
                        bot_name_mentioned = True

            if bot_name_mentioned:
                prompt_parameters = PromptParameters(
                    prompt=payload["event"]["text"],
                    space_id="~622753c759c0740069daf1e1",
                    source={"name": "slack", "id": payload["event"]["channel"]},
                )

                SLACK_CLIENT.chat_postMessage(
                    channel=prompt_parameters.source.id,
                    blocks=LOADING_BLOCK,
                    text=LOADING_INDICATOR,
                )

                # Check if files are attached
                if "files" in payload["event"]:
                    for file_info in payload["event"]["files"]:
                        file_url = file_info["url_private_download"]
                        file_name = file_info["name"]
                        logger.info(
                            f"Handling file: {prompt_parameters.prompt} | {file_name}"
                        )
                        background_tasks.add_task(
                            download_handler,
                            prompt_parameters,
                            file_url,
                            file_name,
                        )
                else:
                    # don't use endpoint function because they will not run in the background
                    background_tasks.add_task(prompt_handler, prompt_parameters)
            else:
                return

    # slack will generate a new event for the bot message, but this except will ignore it
    except KeyError:
        pass
    except Exception as error:
        print(error)

    return JSONResponse(content=payload)


def retrive_slack_messages(channel_id):
    result = SLACK_CLIENT.conversations_history(channel=channel_id, limit=slack_history_limit)
    messages = result["messages"]
    formatted_messages = []
    for message in messages:
        text = message.get('text', '')
        ts = message.get('ts', '')
        user = 'Assistant' if 'bot_id' in message else 'Human' if 'client_msg_id' in message else ''
        formatted_messages.append({'content': text, 'user': user, 'ts': ts})
    return formatted_messages


def check_user(user_id):
    response = SLACK_CLIENT.users_info(user=user_id)
    if response["ok"]:
        user = response["user"]
        # Check if the user is a bot and has a specific real name
        if user["is_bot"] and user["profile"]["real_name"] == SLACK_BOT_DISPLAY_NAME:
            return True
    return False


async def new_user_handler(payload):
    examples = await get_example_prompts()
    user_id = payload["event"]["user"]
    try:
        SLACK_CLIENT.chat_postEphemeral(
            user=user_id,
            channel=payload["event"]["channel"],
            text=f"Welcome to the channel, <@{user_id}>!",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Welcome to the channel, <@{user_id}>! Use @ and a prompt, the last 10 messages will be also available to the model",
                    },
                },
                {"type": "divider"},
            ]
            + examples["blocks"],
        )
    except Exception as e:
        print(f"Error: {e}")


def download_handler(prompt_parameters, file_url, file_name):
    resp = requests.get(
        file_url,
        headers={"Authorization": "Bearer %s" % SLACK_BOT_OAUTH_TOKEN},
        allow_redirects=True,
        stream=True,
    )
    if resp.status_code == 200:
        file_path = f"downloads/{file_name}"

        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_translation_params = {
            "slack_channel_id": prompt_parameters.source.id,
            "file_path": file_path,
        }

        memory_params = history_handler(prompt_parameters)
        conversional_agent = new_conversional_agent(memory=memory_params[1])

        prompt = f"""
        {memory_params[0]}
        System: Parameters for file tools: {file_translation_params}, Ignore any previous errors/warnings
        Human: {prompt_parameters.prompt}
        Assistant:
        """
        
        conversional_agent.run(input=prompt, callbacks=[langfuse_handler])


def prompt_handler(prompt_parameters: PromptParameters):
    memory_params = history_handler(prompt_parameters)
    conversional_agent = new_conversional_agent(memory=memory_params[1])

    prompt = f"""
    {memory_params[0]}
    Human: {prompt_parameters.prompt}
    Assistant:
    """
    # On dev, all slack message is logged
    # On prod, no slck message is logged
    response = conversional_agent.run(input=prompt, callbacks=[langfuse_handler] if is_dev_env else None)
    slack_response_handler(prompt_parameters, response)


def history_handler(prompt_parameters):
    memory = None

    if prompt_parameters.source.name == "slack":
        memory = slack_to_llm_memory(
            slack_client=SLACK_CLIENT, prompt_parameters=prompt_parameters
        )
    else:
        logger.error(
            "Not matching event source found for memory conversion",
            prompt_parameters.source.name,
        )
    logger.info(f"Handling basic prompt: {prompt_parameters.prompt} | {memory}")

    chat_history = ""
    for message in memory.chat_memory.messages:
        if isinstance(message, HumanMessage):
            chat_history += f"user: {message.content}\n"
        elif isinstance(message, AIMessage):
            chat_history += f"ai: {message.content}\n"
        elif isinstance(message, SystemMessage):
            chat_history += f"system: {message.content}\n"
    # due to TypeError: unhashable type: 'ConversationBufferMemory' no dict can be returned
    return [chat_history, memory]


def slack_response_handler(prompt_parameters: PromptParameters, response):
    try:
        response = json.loads(response)
        print(response)
        if "action_input" in response:
            string_handler(prompt_parameters, response["action_input"])
        else:
            SLACK_CLIENT.chat_postMessage(
                channel=prompt_parameters.source.id,
                text="response",
                blocks=response["slack_response"],
            )
    except Exception as error:
        if isinstance(response, str):
            string_handler(prompt_parameters, response)
        else:
            print(f"Error while sending slack reponse: {response}, {str(error)}")


def string_handler(prompt_parameters: PromptParameters, response):
    link_blocks = [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": response,
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Rate my answer"},
            "accessory": {
                "type": "radio_buttons",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Good"},
                        "value": "value-0",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Ok"},
                        "value": "value-1",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Bad"},
                        "value": "value-2",
                    },
                ],
                "action_id": "radio_buttons-action",
            },
        },
    ]
    try:
        SLACK_CLIENT.chat_postMessage(
            channel=prompt_parameters.source.id,
            text=response,
            blocks=link_blocks,
        )
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["ok"] is False
        assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
        print(f"Got an error: {e.response['error']}")
