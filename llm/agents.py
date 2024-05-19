from langchain.agents import (
    load_tools,
    initialize_agent,
    AgentType,
)
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage

from llm.tools.confluence.confluence_tool import confluence_tool
from llm.tools.webpage.webpage_tool import webpage_tool
from llm.tools.git.git_repo_tool import git_tool
from llm.tools.deepl.file_translation_tool import file_translation_tool
from llm.tools.document.document_vector_store_tool import document_vector_store_tool
from llm.tools.image.image_generation_tool import image_generation_tool
from llm.tools.image.image_operations_tool import image_operations_tool
from llm.config import HAIKU_CHAT_MODEL

EMPTY_MEMORY = ConversationBufferMemory(memory_key="chat_history", return_messages=True)


# prompt_parameters: PromptParameters
def new_conversional_agent(chat_model=HAIKU_CHAT_MODEL, memory=EMPTY_MEMORY):
    tools = load_tools(
        # build in tools
        [
            "google-search",
            # "requests_all",
            "llm-math",
        ],
        llm=chat_model,
    ) + [
        confluence_tool,
        webpage_tool,
        git_tool,
        file_translation_tool,
        document_vector_store_tool,
        image_generation_tool,
        image_operations_tool,
    ]

    system_message = f"""
        You are a chat bot which helps the user find answers to his question.
        !You have to answer in the language of the user messages, default is always german!
        !For internal action you are allowed to use english, like function calling!
        Use all past messages within your memory for context.
    """
    system_message = SystemMessage(content=system_message)

    memory.chat_memory.add_message(system_message)

    conversional_agent = initialize_agent(
        tools,
        chat_model,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        memory=memory,
        # max_iterations=3,
    )

    return conversional_agent
