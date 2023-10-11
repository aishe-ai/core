import os
import urllib.parse
import json
import logging

from fastapi import FastAPI, BackgroundTasks, Request, Form
from fastapi.responses import JSONResponse

from dotenv import load_dotenv

from langchain.schema import SystemMessage, HumanMessage, AIMessage

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


from llm.agents import new_conversional_agent
from data_models.models import *
from llm.memory.slack_memory import slack_to_llm_memory
from data_models.constants import LOADING_INDICATOR, LOADING_BLOCK

import requests

logging.config.fileConfig("logging.conf", disable_existing_loggers=False)

# get root logger
logger = logging.getLogger(__name__)


load_dotenv()


SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")

SLACK_CLIENT = WebClient(token=SLACK_BOT_OAUTH_TOKEN)

app = FastAPI()


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

    # Sample list of texts to be added in "blocks"
    sample_texts = [
        "- Normal prompts like in chatgpt:\n\t\t\t- Who is Sam Hyde?",
        "- Google:\n\t\t\t- Wie hoch ist die Regenwahrscheinlichkeit heute in Hannover?\n\t\t\t- Who is Leo DiCaprio's girlfriend? What is her current age raised to the 0.43 power?",
        "- Website:\n\t\t\t- Wo kann ich auf dieser Website meine Fragen einreichen? https://verwaltung.bund.de/portal/DE/ueber\n\t\t\t- Wann endet die Frist für die erste Phase? https://verwaltung.bund.de/leistungsverzeichnis/de/leistung/99148138017000",
        "- Documents:\n\t\t\t- Summarize this document (with attached file)\n\n"
        "- Confluence:\n\t\t\t- Summarize the page: https://...... \n\n"
        "- Git repos:\n\t\t\t- In which language is this project written: https://github.com/martinmimigames/little-music-player?\n\t\t\t- What does HWListener in this project https://github.com/martinmimigames/little-music-player do?\n\t\t\t- What is the difference of the m3u branch in this project: https://github.com/martinmimigames/little-music-player?",
    ]

    # Use a for loop to fill in the text
    for text in sample_texts:
        block = {
            "type": "section",
            "text": {"type": "plain_text", "text": text, "emoji": True},
        }
        blocks.append(block)

    return {"blocks": blocks}


@app.post("/slack/rating/")
async def slack_rating(payload: str = Form(...)):
    # Decode the URL-encoded payload to json
    decoded_payload = urllib.parse.unquote(payload)
    json_payload = json.loads(decoded_payload)

    # # Extract relevant data (customize as needed)
    user_id = json_payload["user"]["id"]
    rating = json_payload["state"]["values"]["UBJT"]["radio_buttons-action"][
        "selected_option"
    ]["text"]["text"]

    print(user_id, rating)

    # logic here (e.g., save to a database, respond back to Slack, etc.)

    return payload


# must return given payload for slack challenge:
# slack retry behaviour
# https://api.slack.com/apis/connections/events-api#retries
@app.post("/slack/event/")
async def new_slack_event(
    request: Request, payload: dict, background_tasks: BackgroundTasks
):
    try:
        if "has joined the channel" in payload["event"]["text"]:
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
                                "text": f"Welcome to the channel, <@{user_id}>!",
                            },
                        },
                        {"type": "divider"},
                    ]
                    + examples["blocks"],
                )
            except Exception as e:
                print(f"Error: {e}")
                return None

        # check if message is from user, bot message has a bot_id key
        if (
            payload["event"]["client_msg_id"]
            and f"@{SLACK_BOT_ID}" in payload["event"]["text"]
        ):
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
                    file_extension = os.path.splitext(file_name)[1]
                    logger.info(
                        f"Handling file: {prompt_parameters.prompt} | {file_name}"
                    )
                    background_tasks.add_task(
                        download_handler,
                        prompt_parameters,
                        file_url,
                        file_name,
                        file_extension,
                    )
            else:
                # dont use endpoint function because they will not run in the background
                background_tasks.add_task(prompt_handler, prompt_parameters)

    # slack will generate a new event for the bot message, but this except will ignore it
    except KeyError:
        pass

    return JSONResponse(content=payload)


def download_handler(prompt_parameters, file_url, file_name, file_extension):
    resp = requests.get(
        file_url,
        headers={"Authorization": "Bearer %s" % SLACK_BOT_OAUTH_TOKEN},
        allow_redirects=True,
        stream=True,
    )
    if resp.status_code == 200:
        documents = []
        file_path = f"downloads/{file_name}"

        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        memory = None
        match prompt_parameters.source.name:
            case "slack":
                memory = slack_to_llm_memory(
                    slack_client=SLACK_CLIENT, prompt_parameters=prompt_parameters
                )
            case other:
                logger.error(
                    "Not matching event source found for memory conversion",
                    prompt_parameters.source.name,
                )
        logger.info(f"Handling basic prompt: {prompt_parameters.prompt} | {memory}")
        conversional_agent = new_conversional_agent(memory=memory)

        chat_history = ""
        for message in memory.chat_memory.messages:
            if isinstance(message, HumanMessage):
                chat_history += f"user: {message.content}\n"
            elif isinstance(message, AIMessage):
                chat_history += f"ai: {message.content}\n"
            elif isinstance(message, SystemMessage):
                chat_history += f"system: {message.content}\n"

        file_translation_params = {
            "slack_channel_id": prompt_parameters.source.id,
            "file_path": file_path,
        }

        prompt = f"""
        {chat_history}
        System: Parameters for file translation: {file_translation_params}, Ignore any previous errors/warnings
        Human: {prompt_parameters.prompt}
        Assistant:
        """

        print(prompt)

        response = conversional_agent.run(input=prompt)


def prompt_handler(prompt_parameters: PromptParameters):
    memory = None
    match prompt_parameters.source.name:
        case "slack":
            memory = slack_to_llm_memory(
                slack_client=SLACK_CLIENT, prompt_parameters=prompt_parameters
            )
        case other:
            logger.error(
                "Not matching event source found for memory conversion",
                prompt_parameters.source.name,
            )
    logger.info(f"Handling basic prompt: {prompt_parameters.prompt} | {memory}")
    conversional_agent = new_conversional_agent(memory=memory)

    chat_history = ""
    for message in memory.chat_memory.messages:
        if isinstance(message, HumanMessage):
            chat_history += f"user: {message.content}\n"
        elif isinstance(message, AIMessage):
            chat_history += f"ai: {message.content}\n"
        elif isinstance(message, SystemMessage):
            chat_history += f"system: {message.content}\n"

    prompt = f"""
    {chat_history}
    Human: {prompt_parameters.prompt}
    Assistant:
    """

    print(prompt)

    response = conversional_agent.run(input=prompt)
    slack_response_handler(prompt_parameters, response)


def slack_response_handler(prompt_parameters: PromptParameters, response):
    try:
        response = json.loads(response)
        try:
            SLACK_CLIENT.chat_postMessage(
                channel=prompt_parameters.source.id,
                text="response",
                blocks=response["slack_response"],
            )
        except SlackApiError as e:
            # You will get a SlackApiError if "ok" is False
            assert e.response["ok"] is False
            assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
            print(f"Got an error: {e.response['error']}")
    except:
        string_handler(prompt_parameters, response)


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
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-action",
            },
            "label": {
                "type": "plain_text",
                "text": "You can tell me more about your rating, if you want.",
                "emoji": True,
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

    print(response)
