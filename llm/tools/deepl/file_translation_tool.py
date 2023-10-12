import requests
import os
import time

from slack_sdk import WebClient

from dotenv import load_dotenv

from langchain.tools import tool

from data_models.models import DeeplDocumentTranslationTool

load_dotenv()

SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")
SLACK_CLIENT = WebClient(token=SLACK_BOT_OAUTH_TOKEN)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = os.getenv("DEEPL_API_URL")


@tool("file translation", return_direct=True, args_schema=DeeplDocumentTranslationTool)
def file_translation_tool(
    file_path: str,
    target_language_abbrevation: str,
    slack_channel_id: str,
) -> str:
    """
    Use this tool for translating a document into a specific language.
    """
    if not os.path.exists(file_path):
        send_error_notification(f"No file found at {file_path}", slack_channel_id)
        return "file not found"
        # raise FileNotFoundError(f"No file found at {file_path}")

    try:
        # Upload the file for translation
        url = DEEPL_API_URL
        headers = {"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"}
        files = {
            "file": (os.path.basename(file_path), open(file_path, "rb")),
        }
        data = {"target_lang": target_language_abbrevation}
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.RequestException as e:
        send_error_notification(f"Failed to upload file: {e}", slack_channel_id)
        raise

    try:
        headers = {
            "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {"document_key": response.json()["document_key"]}
        document_id = response.json()["document_id"]
        while True:
            # Recheck the state of the document every 5 seconds
            time.sleep(5)
            status_response = requests.post(
                f"{DEEPL_API_URL}/{document_id}", headers=headers, json=data
            )
            status_response.raise_for_status()  # Raise an exception for HTTP errors
            if status_response.json().get("status") == "done":
                # If the translation is done, download the translated document
                translation_response = requests.post(
                    f"{DEEPL_API_URL}/{document_id}/result", headers=headers, json=data
                )
                # print(translation_response.json())
                translation_response.raise_for_status()  # Raise an exception for HTTP errors

                # Save the translated document to a file
                new_file_path = f"downloads/{target_language_abbrevation}_{os.path.basename(file_path)}"
                with open(new_file_path, "wb") as new_file:
                    new_file.write(translation_response.content)
                break  # Exit the while loop once the document is translated
    except requests.RequestException as e:
        send_error_notification(
            f"Error during translation process: {e}", slack_channel_id
        )
        raise

    try:
        # Send the Slack message with the file attachment
        SLACK_CLIENT.files_upload(
            channels=slack_channel_id,
            file=new_file_path,
            title=f"Translated Document: {os.path.basename(new_file_path)}",
            initial_comment=f"Translation completed! Here's the translated document.",
        )
    except Exception as e:
        send_error_notification(f"Failed to send file to Slack: {e}", slack_channel_id)
        raise

    os.remove(file_path)
    os.remove(new_file_path)

    return new_file_path  # Return the path to the new file


def send_error_notification(error_message, slack_channel_id):
    SLACK_CLIENT.chat_postMessage(
        channel=slack_channel_id, text=f"Error: {error_message}"
    )
