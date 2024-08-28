import os
import json

from dotenv import load_dotenv

from langchain.tools import tool
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    UnstructuredFileLoader,
)
from langchain.text_splitter import (
    CharacterTextSplitter,
)
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory


from data_models.models import VectorStoreDocumentTool
from llm.vector_store import new_vector_store

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


from data_models.models import *
from llm.config import GPT_4_CHAT_MODEL

load_dotenv()

SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")
SLACK_CLIENT = WebClient(token=SLACK_BOT_OAUTH_TOKEN)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = os.getenv("DEEPL_API_URL")


@tool("document_vector_store", return_direct=True, args_schema=VectorStoreDocumentTool)
def document_vector_store_tool(
    file_path: str, slack_channel_id: str, prompt: str
) -> str:
    """
    Use this tool for answering document related prompts from user.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No file found at {file_path}")

    file_extension = file_path.suffix

    if file_extension == ".docx":
        loader = Docx2txtLoader(str(file_path))
    elif file_extension == ".pdf":
        loader = PyPDFLoader(str(file_path))
    else:
        print(f"Using general purpose loader for {file_extension}")
        loader = UnstructuredFileLoader(str(file_path))

    text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=2000, chunk_overlap=1000
    )
    documents = loader.load_and_split(text_splitter)
    vector_store = new_vector_store(documents)

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="question",
        output_key="answer",
        return_messages=True,
    )

    # https://github.com/hwchase17/chat-your-data
    llm = GPT_4_CHAT_MODEL
    conversation_qa_chain = ConversationalRetrievalChain.from_llm(
        llm,
        retriever=vector_store.as_retriever(),
        memory=memory,
        return_source_documents=True,
    )
    conversation_result = conversation_qa_chain({"question": prompt})

    print(conversation_result)

    link_blocks = [
        {"type": "divider"},
    ]
    link_blocks.append(
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": conversation_result["chat_history"][-1].content,
                "emoji": True,
            },
        }
    )
    link_blocks.append({"type": "divider"})
    link_blocks.append(
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
        }
    )
    link_blocks.append(
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
    )
    SLACK_CLIENT.chat_postMessage(
        channel=slack_channel_id,
        # text=f"{simple_result['result']} || {conversation_result['chat_history'][-1].content}",
        text=conversation_result["chat_history"][-1].content,
        blocks=link_blocks,
    )

    return json.dumps(
        {
            # 'ai_message': conversation_result,
            "slack_response": link_blocks
        }
    )
