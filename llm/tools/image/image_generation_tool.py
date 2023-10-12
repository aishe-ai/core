import requests
import os
import json
import openai

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from dotenv import load_dotenv

from langchain.tools import tool

from data_models.models import ImageCreationTool

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")
SLACK_CLIENT = WebClient(token=SLACK_BOT_OAUTH_TOKEN)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = os.getenv("DEEPL_API_URL")


@tool("image generation", return_direct=True, args_schema=ImageCreationTool)
def image_generation_tool(
    prompt: str,
    slack_channel_id: str,
) -> str:
    """
    Use this tool for generation an image from a prompt.
    """
    try:
        # Send image generation request to DALL-E
        dalle_response = openai.Image.create(
            prompt=prompt, n=3, size="1024x1024"
        )  # Adjust n to 3 for three images
        data = dalle_response["data"]

        blocks = [
            {
                "type": "section",
                "block_id": "sectionBlockOnlyPlainText",
                "text": {
                    "type": "plain_text",
                    "text": "Here a some results.",
                    "emoji": True,
                },
            }
        ]  # Initialize blocks as an empty list to accumulate image blocks
        for idx, item in enumerate(data, 1):  # Start idx at 1 for human-readable IDs
            image_url = item["url"]
            image_title = f"{prompt}-{idx}"  # Format title with prompt and ID

            # Create an image block for each image
            image_block = {
                "type": "image",
                "title": {
                    "type": "plain_text",
                    "text": image_title,
                    "emoji": True,
                },
                "image_url": image_url,
                "alt_text": image_title,
            }
            blocks.append(image_block)  # Add the image block to the blocks list

    except SlackApiError as e:
        # Print error if Slack request fails
        print(f"Error: {e.response['error']}")
    except Exception as e:
        # Print any other errors
        print(f"An error occurred: {str(e)}")

    return json.dumps(
        {
            # 'ai_message': conversation_result,
            "slack_response": blocks
        }
    )
