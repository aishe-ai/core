from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

HAIKU_CHAT_MODEL = ChatAnthropic(model_name="claude-3-haiku-20240307", temperature=1)
GPT4_CHAT_MODEL = ChatOpenAI(model_name="gpt-4", temperature=0.4)
