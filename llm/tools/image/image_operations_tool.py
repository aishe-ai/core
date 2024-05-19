import os
import json
import openai
import base64
import requests

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from dotenv import load_dotenv

from langchain.tools import tool

from data_models.models import ImageEditingTool

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")
SLACK_CLIENT = WebClient(token=SLACK_BOT_OAUTH_TOKEN)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = os.getenv("DEEPL_API_URL")


def send_error_notification(error_message, slack_channel_id):
    SLACK_CLIENT.chat_postMessage(
        channel=slack_channel_id, text=f"Error: {error_message}"
    )


def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


@tool("image operations", return_direct=True, args_schema=ImageEditingTool)
def image_operations_tool(prompt: str, slack_channel_id: str, url: str) -> str:
    """
    Use this tool for operation on images from a prompt.
    """

    image_url = ""
    if not os.path.exists(url):
        image_url = url
    else:
        image_url = "data:image/jpeg;base64," + image_to_base64(url)

    print(image_url)
    try:
        gpt_4_response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                }
            ],
        )
        data = gpt_4_response["choices"]
        blocks = [
            {
                "type": "section",
                "block_id": "sectionBlockOnlyPlainText",
                "text": {
                    "type": "plain_text",
                    "text": data[0]["message"]["content"],
                    "emoji": True,
                },
            }
        ]
    except SlackApiError as e:
        print(f"Error: {e.response['error']}")
        blocks = []  # Define blocks in case of error
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        blocks = []  # Define blocks in case of error

    return json.dumps({"slack_response": blocks})
