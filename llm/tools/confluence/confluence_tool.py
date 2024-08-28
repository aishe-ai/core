import os
import json
from dotenv import load_dotenv

from langchain.chains import ConversationalRetrievalChain
from langchain.tools import tool
from langchain_community.document_loaders import ConfluenceLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage

from data_models.models import ConfluenceToolParams
from llm.vector_store import new_vector_store
from llm.config import HAIKU_CHAT_MODEL

load_dotenv()

CONFLUENCE_API_KEY = os.getenv("CONFLUENCE_API_KEY")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")


@tool("confluence_search", args_schema=ConfluenceToolParams, return_direct=True)
def confluence_tool(
    prompt: str, url: str, confluence_space_id: str, confluence_page_id: str
) -> str:
    """
    Use this tool for handling a prompt regarding a confluence page.
    """

    loader = ConfluenceLoader(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_USERNAME,
        api_key=CONFLUENCE_API_KEY,
    )

    # overlap for better cohesion between chunks
    splitter = CharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=2000, chunk_overlap=1000
    )

    # includes ocr for images, space_key=confluence_space_id,
    documents = loader.load(space_key=confluence_space_id, include_attachments=True)
    if (
        confluence_page_id
        and confluence_page_id != "None"
        and confluence_space_id != "null"
    ):
        documents = loader.load(page_ids=[confluence_page_id], include_attachments=True)

    print(len(documents))
    splitted_documents = splitter.split_documents(documents)
    vector_store = new_vector_store(splitted_documents)

    llm = HAIKU_CHAT_MODEL

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="question",
        output_key="answer",
        return_messages=True,
    )

    system_message = f"""
        You are an assistant which helps to user find answers to his question with internal company data.
        This data will be provided by a vector db as context.
        You also help with normal stuff like answering questions or generating text by ignoring this system message.
        When asked to summarize a specific page only summarize pages which match the page id within the url if appliable.
    """
    system_message = SystemMessage(content=system_message)

    memory.chat_memory.add_message(system_message)
    conversation_qa_chain = ConversationalRetrievalChain.from_llm(
        llm,
        retriever=vector_store.as_retriever(),
        memory=memory,
        return_source_documents=True,
    )
    conversation_result = conversation_qa_chain({"question": prompt})

    link_blocks = list(
        map(source_object_to_slack_block, conversation_result["source_documents"])
    )
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
    return json.dumps(
        {
            # 'ai_message': conversation_result,
            "slack_response": link_blocks
        }
    )


def source_object_to_slack_block(source_document):
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": source_document.metadata["title"]},
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": "Link", "emoji": True},
            "value": "test1",
            "url": source_document.metadata["source"],
            "action_id": "button-action",
        },
    }
