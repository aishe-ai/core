from langchain.chat_models import ChatOpenAI
from langchain.agents import (
    load_tools,
    initialize_agent,
    AgentType,
)
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI

from llm.tools.confluence.confluence_tool import confluence_tool
from llm.tools.webpage.webpage_tool import webpage_tool
from llm.tools.git.git_repo_tool import git_tool

EMPTY_MEMORY = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
DEFAULT_CHAT_MODEL = ChatOpenAI(model_name="gpt-4", temperature=0.4)


# prompt_parameters: PromptParameters
def new_conversional_agent(chat_model=DEFAULT_CHAT_MODEL, memory=EMPTY_MEMORY):
    tools = load_tools(
        # build in tools
        [
            "google-search",
            # "requests_all",
            "llm-math",
        ],
        llm=chat_model,
    ) + [confluence_tool, webpage_tool, git_tool]

    conversional_agent = initialize_agent(
        tools,
        chat_model,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        memory=memory,
    )

    return conversional_agent
