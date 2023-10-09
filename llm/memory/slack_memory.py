from slack_sdk.errors import SlackApiError

from langchain.memory import ConversationBufferMemory

from data_models.models import PromptParameters
from data_models.constants import LOADING_INDICATOR, CUSTOM_SLACK_COMMANDS


def slack_to_llm_memory(slack_client, prompt_parameters: PromptParameters, limit=10):
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        # input_key="input",
        # output_key="answer",
        return_messages=True,
    )

    try:
        # Fetch the last 100 messages (maximum limit)
        response = slack_client.conversations_history(
            channel=prompt_parameters.source.id, limit=limit
        )

        messages = response["messages"]

        non_command_messages = [
            message
            for message in messages
            # "bot_id" not in message and
            if message["text"] not in ([LOADING_INDICATOR] + CUSTOM_SLACK_COMMANDS)
        ]

        for message in reversed(non_command_messages):
            if "bot_id" in message:
                # This is a bot message
                memory.chat_memory.add_ai_message(message["text"])
            else:
                # This is a user message
                memory.chat_memory.add_user_message(message["text"])
        return memory
    except SlackApiError as e:
        print(f"Error: {e.response['error']}")
