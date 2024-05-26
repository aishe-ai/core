from typing import Optional
from pydantic import BaseModel, Field
import json
import os
from dotenv import load_dotenv

from langchain.chains import ConversationalRetrievalChain
from langchain.tools import tool
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage


from llm.config import GPT_3_5_CHAT_MODEL
from data_models.models import PgVectorToolParams
from llm.vector_store import new_pgvector_store
from llm.vectorstores.pgvector.non_rbac import NonRBACVectorStore

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@tool("pgvector search", args_schema=PgVectorToolParams, return_direct=True)
def pgvector_tool(prompt: str) -> str:
    """
    Use this tool for handling a prompt which asks needs retrieval augmented generation(rag).
    Current knowlegde within the db:
    - Titanic passenger/crew information
    """

    llm = GPT_3_5_CHAT_MODEL

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="question",
        output_key="answer",
        return_messages=True,
    )

    system_message = f"""
        You are an assistant which helps the user find answers to their question by searching a vector database.
        This data will be provided by the vector db as context.
        You also help with normal stuff like answering questions or generating text by ignoring this system message.
    """
    system_message = SystemMessage(content=system_message)

    memory.chat_memory.add_message(system_message)
    conversation_qa_chain = ConversationalRetrievalChain.from_llm(
        llm,
        retriever=NonRBACVectorStore().as_retriever(),
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
    return json.dumps({"slack_response": link_blocks})


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
