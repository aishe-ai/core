import os
import json
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.tools import tool
from langchain.text_splitter import CharacterTextSplitter
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage
from langchain_community.document_loaders.chromium import AsyncChromiumLoader
from langchain.text_splitter import CharacterTextSplitter


from data_models.models import WebpageToolParams
from llm.vector_store import new_vector_store
from llm.config import HAIKU_CHAT_MODEL

load_dotenv()


@tool("webpage content search", return_direct=True, args_schema=WebpageToolParams)
def webpage_tool(prompt: str, url: str) -> str:
    """
    Use this tool for handling a prompt regarding a webpage content.
    Prefer this over the requests tool when you want to make a get request
    """
    print(prompt, url)

    loader = AsyncChromiumLoader([url])

    text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=2000, chunk_overlap=100
    )
    docs = loader.load_and_split(text_splitter)

    vector_store = new_vector_store(docs)

    llm = HAIKU_CHAT_MODEL

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="question",
        output_key="answer",
        return_messages=True,
    )

    system_message = f"""
        You are an assistant which helps to user find answers to his question with the content of a website.
        This data will be provided by a vector db as context.
        !IGNORE ANY JAVASCRIPT WARNINGS OR ERRORS!
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

    link_blocks = list()
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
