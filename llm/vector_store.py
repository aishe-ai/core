import os

from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores.pgvector import PGVector

from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = PGVector.connection_string_from_db_params(
    driver=os.environ.get("PGVECTOR_DRIVER", "psycopg2"),
    host=os.environ.get("PGVECTOR_HOST", "localhost"),
    port=int(os.environ.get("PGVECTOR_PORT", "5432")),
    database=os.environ.get("PGVECTOR_DATABASE", "aisheAI"),
    user=os.environ.get("POSTGRES_USER", "aisheAI"),
    password=os.environ.get("POSTGRES_PASSWORD", "password"),
)

print(CONNECTION_STRING)


def new_vector_store(documents):
    return Chroma.from_documents(documents, OpenAIEmbeddings())
