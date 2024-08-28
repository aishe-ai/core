import json
import shutil
import re

from langchain.chains import ConversationalRetrievalChain
from langchain.tools import tool
from langchain.text_splitter import CharacterTextSplitter
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage
from langchain.text_splitter import CharacterTextSplitter
from git import Repo
from langchain_community.document_loaders import GitLoader

from data_models.models import GitToolParams
from llm.vector_store import new_vector_store
from data_models.constants import ALLOWED_FILE_EXTENSIONS
from llm.config import GPT_4_CHAT_MODEL


@tool("git_search", return_direct=True, args_schema=GitToolParams)
def git_tool(prompt: str, url: str, project_name: str, branch_name: str) -> str:
    """
    Use this tool for handling a prompt regarding a repo, when given its url by the user
    """
    folder_path = f"downloads/{project_name}"

    Repo.clone_from(url, to_path=folder_path)

    loader = GitLoader(
        repo_path=folder_path,
        file_filter=lambda file_path: file_path.endswith(ALLOWED_FILE_EXTENSIONS),
    )

    text_splitter = CharacterTextSplitter(chunk_size=2000, chunk_overlap=0)
    docs = loader.load_and_split(text_splitter)
    vector_store = new_vector_store(docs)

    shutil.rmtree(folder_path)

    llm = GPT_4_CHAT_MODEL

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="question",
        output_key="answer",
        return_messages=True,
    )

    system_message = f"""
        You are an assistant which helps to user find answers to his question with the content of a website.
        This data will be provided by a vector db as context.
        Ignore context from xml files
    """
    system_message = SystemMessage(content=system_message)

    memory.chat_memory.add_message(system_message)

    retriever = vector_store.as_retriever()
    retriever.search_kwargs["distance_metric"] = "cos"
    retriever.search_kwargs["fetch_k"] = 100
    retriever.search_kwargs["maximal_marginal_relevance"] = True
    retriever.search_kwargs["k"] = 10

    conversation_qa_chain = ConversationalRetrievalChain.from_llm(
        llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
    )
    conversation_result = conversation_qa_chain({"question": prompt})

    # link_blocks = list()
    link_blocks = list(
        map(
            lambda doc: source_object_to_slack_block(url, branch_name, doc),
            conversation_result["source_documents"][:2],
        )
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


def source_object_to_slack_block(url, branch_name, source_document):
    pattern = r"[^/]+$"

    file_name_match = re.search(pattern, source_document.metadata["source"])
    file_name = file_name_match.group()

    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": file_name},
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": "Link", "emoji": True},
            "value": "test1",
            "url": f"{url}/blob/{branch_name}/{source_document.metadata['source']}",
            "action_id": "button-action",
        },
    }
