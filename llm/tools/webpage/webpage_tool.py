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
from langchain_community.document_loaders import FireCrawlLoader

from langchain_community.chat_models import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain


from data_models.models import WebpageToolParams
from llm.config import GPT_4_CHAT_MODEL


load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")


@tool("webpage_content_search", return_direct=True, args_schema=WebpageToolParams)
def webpage_tool(prompt: str, url: str, ingestion_mode: str = "scrape") -> str:
    """
    Use this tool for handling a prompt regarding a webpage content.
    Prefer this over the requests tool when you want to make a get request
    """

    fire_loader = FireCrawlLoader(
        api_key=FIRECRAWL_API_KEY, url=url, mode=ingestion_mode
    )

    fire_docs = fire_loader.load()

    system_message = f"""
        You are an assistant which helps to user find answers to his question with the content of a website.
        This data will be provided by a vector db as context.
        Always respond with the prompt language, default always to english, if unclear.
        !!!YOU ARE NOT ALLOWED TO ANSWER IN A LANGUAGE WHICH IS NOT USED IN THE INPUT PROMPT, DEFAULT TO ENGLISH!!
        !IGNORE ANY JAVASCRIPT WARNINGS OR ERRORS!
        Use the below context for answer the user prompt:
        {{context}}
    """

    llm = GPT_4_CHAT_MODEL

    messages = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_message,
            ),
            ("user", prompt),
        ]
    )
    chain = create_stuff_documents_chain(llm, messages)

    conversation_result = chain.invoke({"context": fire_docs})

    link_blocks = list()
    link_blocks.append(
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": conversation_result,
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
