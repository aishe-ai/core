from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector

from llm.config import CONNECTION_STRING


def new_vector_store(documents):
    vector_store = PGVector(
        embeddings=OpenAIEmbeddings(),
        collection_name="document",
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )

    vector_store.add_documents(documents)

    return vector_store
