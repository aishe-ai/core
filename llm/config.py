import os

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

HAIKU_CHAT_MODEL = ChatAnthropic(model_name="claude-3-haiku-20240307", temperature=0.4)
GPT4_CHAT_MODEL = ChatOpenAI(model_name="gpt-4-turbo", temperature=0.4)
GPT_3_5_CHAT_MODEL = ChatOpenAI(model_name="gpt-3.5-turbo-0125", temperature=0.4)

CONNECTION_STRING = f"postgresql://{os.environ.get('POSTGRES_USER', 'aisheAI')}:{os.environ.get('POSTGRES_PASSWORD', 'password')}@{os.environ.get('PGVECTOR_HOST', 'localhost')}:{os.environ.get('PGVECTOR_PORT', '5432')}/{os.environ.get('PGVECTOR_DATABASE', 'aisheAI')}"